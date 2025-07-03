import json
import importlib
import logging
import time
from pathlib import Path
from typing import List, Any, Generator, Dict
import redis
from video_ai_system.config import Settings
from video_ai_system.modules.module_interface import VideoModule
from video_ai_system.modules.sampling_policy import (
    FixedRateSamplingPolicy,
    LearnedSamplingPolicy,
    SamplingPolicy,
)
from video_ai_system.modules.safety_guard import AccuracyMonitor, SafetyGuard
from video_ai_system.services.model_registry_service import ModelRegistryService
from video_ai_system.services.shadow_testing_service import ShadowTestingService
from video_ai_system.services.inference_router import InferenceRouter
from video_ai_system.services.comparison_service import ComparisonService

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Encapsulates the logic for loading and executing processing pipelines,
    adapting its behavior based on the system's operational state.
    """
    ADAPTATION_KEY = "system:adaptation_level"
    DEFAULT_LEVEL = "NORMAL"

    def __init__(
        self,
        model_registry_service: ModelRegistryService,
        shadow_testing_service: ShadowTestingService,
        inference_router: InferenceRouter,
        comparison_service: ComparisonService,
        redis_client: redis.Redis,
        adaptation_config: Dict[str, Any],
        settings: Settings,
    ):
        self.pipelines: Dict[str, List[VideoModule]] = {}
        self.model_registry_service = model_registry_service
        self.shadow_testing_service = shadow_testing_service
        self.inference_router = inference_router
        self.comparison_service = comparison_service
        self.redis_client = redis_client
        self.adaptation_config = adaptation_config
        self.settings = settings

        # The accuracy monitor is shared between the guard and the service
        self.accuracy_monitor = AccuracyMonitor(
            accuracy_drop_threshold=settings.sampling.safety_guards.accuracy_drop_threshold
        )
        self.sampling_policy = self._create_sampling_policy()

        # Inject comparison_service into shadow_testing_service
        self.shadow_testing_service.comparison_service = self.comparison_service

    def load_from_config(self, config_path_str: str):
        """Loads and initializes pipelines from a config file."""
        config_path = Path(config_path_str)
        if not config_path.is_file():
            raise RuntimeError(f"Configuration file not found at {config_path}")

        with config_path.open() as f:
            config = json.load(f)

        self.load_from_config_dict(config)

    def load_from_config_dict(self, config: dict):
        """Loads and initializes pipelines from a configuration dictionary."""
        pipelines_config = config.get("pipelines", {})

        for pipeline_name, pipeline_modules in pipelines_config.items():
            pipeline = []
            for module_config in pipeline_modules:
                module_name = module_config.get("module_name")
                if not module_name:
                    raise RuntimeError(
                        f"Module config in pipeline '{pipeline_name}' missing 'module_name': {module_config}"
                    )

                try:
                    module_path = f"video_ai_system.modules.{module_name}"
                    imported_module = importlib.import_module(module_path)
                    class_name = "".join(
                        word.capitalize() for word in module_name.split("_")
                    )
                    module_class = getattr(imported_module, class_name)

                    # Inject dependencies based on module type
                    if class_name == "ShadowingModule":
                        instance = module_class(
                            module_config=module_config,
                            model_registry_service=self.model_registry_service,
                            shadow_testing_service=self.shadow_testing_service,
                            inference_router=self.inference_router,
                        )
                    else:
                        instance = module_class(
                            module_config=module_config,
                            model_registry_service=self.model_registry_service,
                        )

                    instance.initialize(module_config.get("module_params", {}))
                    pipeline.append(instance)
                except (ModuleNotFoundError, AttributeError) as e:
                    raise RuntimeError(
                        f"Failed to load module '{module_name}' in pipeline '{pipeline_name}': {e}"
                    )

            self.pipelines[pipeline_name] = pipeline
            loaded_modules = [p.__class__.__name__ for p in pipeline]
            print(
                f"PipelineService loaded '{pipeline_name}' pipeline: {' -> '.join(loaded_modules)}"
            )

    def _get_adaptation_level(self) -> str:
        """Reads the current adaptation level from Redis, with fault tolerance."""
        try:
            level_bytes = self.redis_client.get(self.ADAPTATION_KEY)
            if level_bytes:
                return level_bytes.decode('utf-8')
            logger.warning(f"'{self.ADAPTATION_KEY}' not found in Redis. Defaulting to {self.DEFAULT_LEVEL}.")
            return self.DEFAULT_LEVEL
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}. Defaulting to {self.DEFAULT_LEVEL}.")
            return self.DEFAULT_LEVEL
        except Exception as e:
            logger.error(f"An unexpected error occurred while reading from Redis: {e}. Defaulting to {self.DEFAULT_LEVEL}.")
            return self.DEFAULT_LEVEL

    def execute_pipeline(self, pipeline_name: str, initial_data: Any) -> List[Any]:
        """
        Executes a specific named pipeline. Correctly handles generator modules.
        """
        time.sleep(5)
        pipeline = self.pipelines.get(pipeline_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{pipeline_name}' not found.")

        adaptation_level = self._get_adaptation_level()
        logger.info(f"Executing pipeline '{pipeline_name}' with adaptation level '{adaptation_level}'")

        # The first module might be a generator (e.g., DataCollectionModule)
        first_module = pipeline[0]

        # Dynamically adjust parameters based on adaptation level
        if adaptation_level in ["DEGRADED", "CRITICAL"]:
            level_config = self.adaptation_config.get(adaptation_level, {})
            param_overrides = level_config.get("parameter_overrides", {})
            if param_overrides:
                logger.info(f"Applying parameter overrides for {adaptation_level} level: {param_overrides}")
                # This assumes the first module is the one to be adjusted, e.g., Preprocessing
                first_module.update_params(param_overrides)

        data_stream = first_module.process(initial_data)

        # The rest of the pipeline processes each item from the stream
        processing_pipeline = pipeline[1:]

        final_results = []
        if isinstance(data_stream, Generator):
            for item in data_stream:
                # The 'item' is now a dictionary of features for a frame
                if self.sampling_policy.should_process(item):
                    processed_item = item
                    for module in processing_pipeline:
                        processed_item = module.process(processed_item)
                    final_results.append(processed_item)

                    # This is where we would record the accuracy proxy metric
                    # For now, we'll assume a placeholder value.
                    # In a real scenario, this would come from the processed_item
                    proxy_metric_value = processed_item.get("highest_confidence", 0.0)
                    
                    # Determine if the baseline is active for the accuracy monitor
                    is_baseline = not isinstance(self.sampling_policy, (LearnedSamplingPolicy, SafetyGuard))
                    if isinstance(self.sampling_policy, SafetyGuard):
                        is_baseline = self.sampling_policy.is_fallback_active

                    self.accuracy_monitor.record_metric(proxy_metric_value, is_baseline=is_baseline)
        elif not processing_pipeline:
            # If there's only one module and it's not a generator, its output is the final result
            final_results.append(data_stream)
        else:
            # If the first module is not a generator, process its single output
            processed_item = data_stream
            for module in processing_pipeline:
                processed_item = module.process(processed_item)
            final_results.append(processed_item)

        return final_results

    def get_pipeline(self, name: str) -> List[VideoModule]:
        """Returns the specified pipeline."""
        return self.pipelines.get(name, [])

    def _create_sampling_policy(self) -> SamplingPolicy:
        """Factory method to create the sampling policy based on config."""
        config = self.settings.sampling
        policy_type = config.policy.lower()
        logger.info(f"Creating sampling policy of type: '{policy_type}'")

        if policy_type == "learned":
            if not config.learned_policy:
                raise ValueError("Learned policy selected but no configuration provided.")
            
            primary_policy = LearnedSamplingPolicy(
                policy_model_path=config.learned_policy.model_path,
                feature_extractor_model_path=config.learned_policy.feature_extractor_model_path,
            )

            if config.safety_guards.enabled:
                fallback_policy = FixedRateSamplingPolicy(rate_fps=config.heuristic_policy.rate_fps)
                guard = SafetyGuard(
                    primary_policy=primary_policy,
                    fallback_policy=fallback_policy,
                    latency_threshold_ms=config.safety_guards.latency_threshold_ms,
                    accuracy_drop_threshold=config.safety_guards.accuracy_drop_threshold,
                    cooldown_period_minutes=config.safety_guards.cooldown_period_minutes,
                )
                # Inject the shared monitor
                guard.set_accuracy_monitor(self.accuracy_monitor)
                return guard
            return primary_policy

        elif policy_type == "heuristic":
            # The design now favors a content-aware heuristic over a fixed rate one.
            return HeuristicSamplingPolicy(motion_threshold=config.heuristic_policy.motion_threshold)

        elif policy_type == "fixed_rate":
            return FixedRateSamplingPolicy(rate_fps=config.heuristic_policy.rate_fps)

        else:
            raise ValueError(f"Unknown sampling policy type: {policy_type}")