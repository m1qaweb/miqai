"""
This module contains the AI Decision Engine, which is responsible for
dynamically selecting the best AI model for a given task based on
performance and cost metrics.
"""
import mlflow

class AIDecisionEngine:
    """
    A simple AI Decision Engine that selects a model based on tracked metrics.
    """

    def __init__(self, tracking_uri: str):
        """
        Initializes the AI Decision Engine.

        Args:
            tracking_uri: The URI of the MLflow tracking server.
        """
        mlflow.set_tracking_uri(tracking_uri)

    def select_model(self, task: str, user_tier: str = "standard") -> str:
        """
        Dynamically selects a model based on tracked metrics.

        Args:
            task: The task for which to select a model (e.g., "summarization").
            user_tier: The user's subscription tier (e.g., "standard", "premium").

        Returns:
            The name of the selected model.
        """
        if user_tier == "premium":
            # Fetch the best-performing model from MLflow for the given task
            runs = mlflow.search_runs(
                filter_string=f"tags.task = '{task}'",
                order_by=["metrics.quality DESC"],
                max_results=1,
            )
            if not runs.empty:
                return runs.iloc[0]["tags.model_name"]
        
        # Default to a cost-effective model for standard tier or if no premium model is found
        return "gemini-1.5-flash"