import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Constants for API endpoints and parameters
API_BASE_PATH = "/api"
PROJECTS_ENDPOINT = f"{API_BASE_PATH}/projects"
TASKS_ENDPOINT = f"{API_BASE_PATH}/tasks"
DATA_ENDPOINT_SUFFIX = "/data"
ANNOTATIONS_ENDPOINT_SUFFIX = "/annotations"

# Constants for dictionary keys
KEY_RESULTS = "results"
KEY_ID = "id"
KEY_NAME = "name"
KEY_STATUS = "status"
KEY_PROJECT_ID = "project_id"

# Other constants
DEFAULT_ANNOTATION_FORMAT = "CVAT for images 1.1"
ANNOTATION_POLL_INTERVAL_S = 2
DEFAULT_IMAGE_TYPE = "image/jpeg"


class CVATService:
    """
    A service to interact with the CVAT API for creating projects, tasks, and uploading data.
    """

    def __init__(self, cvat_url: str, username: str, password: str):
        """
        Initializes the CVATService with connection details.

        Args:
            cvat_url (str): The base URL of the CVAT instance.
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self.cvat_url = cvat_url.rstrip("/")
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        logger.info(f"CVATService initialized for URL: {self.cvat_url}")

    def _get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Helper to find a project by its name."""
        projects_url = f"{self.cvat_url}{PROJECTS_ENDPOINT}"
        try:
            response = self.session.get(projects_url, params={"search": project_name})
            response.raise_for_status()
            projects = response.json().get(KEY_RESULTS, [])
            for project in projects:
                if project.get(KEY_NAME) == project_name:
                    return project
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get projects from CVAT: {e}")
        return None

    def get_or_create_project(self, project_name: str) -> Optional[int]:
        """
        Finds an existing CVAT project by name or creates it if it doesn't exist.

        Args:
            project_name (str): The name of the project.

        Returns:
            Optional[int]: The ID of the project, or None if an error occurred.
        """
        project = self._get_project_by_name(project_name)
        if project:
            project_id = project.get(KEY_ID)
            logger.info(
                f"Found existing project '{project_name}' with ID: {project_id}"
            )
            return project_id

        logger.info(f"Project '{project_name}' not found, creating a new one.")
        projects_url = f"{self.cvat_url}{PROJECTS_ENDPOINT}"
        try:
            response = self.session.post(projects_url, json={KEY_NAME: project_name})
            response.raise_for_status()
            new_project = response.json()
            new_project_id = new_project.get(KEY_ID)
            logger.info(
                f"Successfully created project '{project_name}' with ID: {new_project_id}"
            )
            return new_project_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create project '{project_name}': {e}")
            return None

    def create_task(self, project_id: int, task_name: str) -> Optional[int]:
        """
        Creates a new annotation task within a project.

        Args:
            project_id (int): The ID of the project to create the task in.
            task_name (str): The name of the new task.

        Returns:
            Optional[int]: The ID of the created task, or None if an error occurred.
        """
        tasks_url = f"{self.cvat_url}{TASKS_ENDPOINT}"
        payload = {KEY_NAME: task_name, KEY_PROJECT_ID: project_id}
        try:
            response = self.session.post(tasks_url, json=payload)
            response.raise_for_status()
            task = response.json()
            task_id = task.get(KEY_ID)
            logger.info(f"Successfully created task '{task_name}' with ID: {task_id}")
            return task_id
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to create task '{task_name}' in project {project_id}: {e}"
            )
            return None

    def upload_data(self, task_id: int, frame_data: bytes, frame_name: str) -> bool:
        """
        Uploads a frame (as a file) to the specified task.

        Args:
            task_id (int): The ID of the task to upload data to.
            frame_data (bytes): The binary data of the frame.
            frame_name (str): The filename for the frame (e.g., 'frame_001.jpg').

        Returns:
            bool: True if the upload was successful, False otherwise.
        """
        data_url = f"{self.cvat_url}{TASKS_ENDPOINT}/{task_id}{DATA_ENDPOINT_SUFFIX}"
        files = {"client_files[0]": (frame_name, frame_data, DEFAULT_IMAGE_TYPE)}
        try:
            # The 'data' payload can specify image quality, etc.
            # For simplicity, we are only sending the files.
            response = self.session.post(data_url, files=files)
            response.raise_for_status()
            logger.info(f"Successfully uploaded data to task {task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload data to task {task_id}: {e}")
            return False

    def get_completed_tasks(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all tasks with 'completed' status for a given project.
        Args:
            project_id (int): The ID of the project.
        Returns:
            A list of completed tasks, or an empty list if none are found or an error occurs.
        """
        tasks_url = f"{self.cvat_url}{TASKS_ENDPOINT}"
        params = {KEY_PROJECT_ID: project_id, KEY_STATUS: "completed"}
        try:
            response = self.session.get(tasks_url, params=params)
            response.raise_for_status()
            tasks = response.json().get(KEY_RESULTS, [])
            logger.info(f"Found {len(tasks)} completed tasks for project {project_id}")
            return tasks
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get completed tasks for project {project_id}: {e}")
            return []

    def get_task_annotations(
        self, task_id: int, format: str = DEFAULT_ANNOTATION_FORMAT
    ) -> Optional[bytes]:
        """
        Downloads annotations for a specific task.
        Args:
            task_id (int): The ID of the task.
            format (str): The export format for the annotations.
        Returns:
            Optional[bytes]: The annotation data as bytes, or None if an error occurred.
        """
        annotations_url = (
            f"{self.cvat_url}{TASKS_ENDPOINT}/{task_id}{ANNOTATIONS_ENDPOINT_SUFFIX}"
        )
        params = {"format": format, "action": "download"}
        try:
            # CVAT might take time to create the export, so we need to handle the 201 Created status and poll
            response = self.session.get(annotations_url, params=params, stream=True)
            response.raise_for_status()

            # The initial request returns a 201 if the export is being prepared.
            # We need to poll the 'Location' header to get the final result.
            while response.status_code == 201:
                location_url = response.headers["Location"]
                logger.info(
                    f"Annotation export for task {task_id} is being prepared. Polling {location_url}..."
                )
                time.sleep(ANNOTATION_POLL_INTERVAL_S)  # Wait before polling
                response = self.session.get(location_url, stream=True)
                response.raise_for_status()

            if response.status_code == 200:
                logger.info(f"Successfully downloaded annotations for task {task_id}")
                return response.content
            else:
                logger.error(
                    f"Failed to download annotations for task {task_id}. Status: {response.status_code}, Body: {response.text}"
                )
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get annotations for task {task_id}: {e}")
            return None

    def delete_task(self, task_id: int) -> bool:
        """
        Deletes a task from CVAT.
        Args:
            task_id (int): The ID of the task to delete.
        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        task_url = f"{self.cvat_url}{TASKS_ENDPOINT}/{task_id}"
        try:
            response = self.session.delete(task_url)
            response.raise_for_status()
            logger.info(f"Successfully deleted task {task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False
