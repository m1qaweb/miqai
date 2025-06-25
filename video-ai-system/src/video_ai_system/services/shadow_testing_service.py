import logging
from typing import Dict, Any, Set

from video_ai_system.services.inference_service import InferenceService


class ShadowTestingService:
    """
    A service to run a candidate model's inference in "shadow mode" against the
    production model and log the comparison for analysis.
    """

    def __init__(self, inference_service: InferenceService, logger: logging.Logger):
        """
        Initializes the ShadowTestingService.

        :param inference_service: The service to use for running model inference.
        :param logger: A logger instance for structured logging of results.
        """
        self.inference_service = inference_service
        self.logger = logger

    async def compare_and_log(
        self,
        video_id: str,
        production_model_id: str,
        candidate_model_id: str,
        production_results: Dict[str, Any],
        production_latency: float,
        video_path: str,
    ):
        """
        Runs inference with a candidate model, compares its results to the
        production model's, and logs the comparison metrics.

        :param video_id: The ID of the video being processed.
        :param production_model_id: The ID of the production model.
        :param candidate_model_id: The ID of the candidate model.
        :param production_results: The inference results from the production model.
        :param production_latency: The inference latency of the production model.
        :param video_path: The path to the video file for candidate inference.
        """
        self.logger.info(
            f"Starting shadow analysis for video_id: {video_id} with candidate: {candidate_model_id}"
        )

        # 1. Run candidate inference
        cand_results, cand_latency = await self.inference_service.analyze(
            video_path, candidate_model_id
        )

        # 2. Calculate comparison metrics
        comparison_metrics = self._calculate_metrics(
            production_results, cand_results
        )

        # 3. Structure and log the final result
        log_payload = {
            "message": "shadow_test_result",
            "video_id": video_id,
            "production_model_id": production_model_id,
            "candidate_model_id": candidate_model_id,
            "production_latency_ms": int(production_latency * 1000),
            "candidate_latency_ms": int(cand_latency * 1000),
            **comparison_metrics,
        }

        self.logger.info(log_payload)
        self.logger.info(
            f"Finished shadow analysis for video_id: {video_id}. Duration: {cand_latency:.2f}s"
        )

    def _calculate_metrics(
        self, prod_res: Dict[str, Any], cand_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates a rich set of comparison metrics between two inference results.
        """
        prod_detections = prod_res.get("detections", [])
        cand_detections = cand_res.get("detections", [])

        prod_classes: Set[str] = {d["label"] for d in prod_detections}
        cand_classes: Set[str] = {d["label"] for d in cand_detections}

        intersection = len(prod_classes.intersection(cand_classes))
        union = len(prod_classes.union(cand_classes))
        jaccard_similarity = intersection / union if union > 0 else 1.0

        prod_confidences = [d["confidence"] for d in prod_detections]
        cand_confidences = [d["confidence"] for d in cand_detections]

        return {
            "detection_count_prod": len(prod_detections),
            "detection_count_cand": len(cand_detections),
            "class_jaccard_similarity": round(jaccard_similarity, 4),
            "classes_only_in_prod": sorted(list(prod_classes - cand_classes)),
            "classes_only_in_cand": sorted(list(cand_classes - prod_classes)),
            "avg_confidence_prod": round(sum(prod_confidences) / len(prod_confidences), 4)
            if prod_confidences
            else 0.0,
            "avg_confidence_cand": round(sum(cand_confidences) / len(cand_confidences), 4)
            if cand_confidences
            else 0.0,
        }