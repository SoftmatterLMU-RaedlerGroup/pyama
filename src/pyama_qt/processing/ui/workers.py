from PySide6.QtCore import QObject, Signal


class WorkflowWorker(QObject):
	"""Worker class for running workflow processing in a separate thread."""

	finished = Signal(bool, str)  # success, message

	def __init__(self, workflow_coordinator, nd2_path, data_info, output_dir, params):
		super().__init__()
		self.workflow_coordinator = workflow_coordinator
		self.nd2_path = nd2_path
		self.data_info = data_info
		self.output_dir = output_dir
		self.params = params

	def run_processing(self):
		"""Run the workflow processing."""
		try:
			# Extract FOV and batch parameters
			fov_start = self.params.get("fov_start", 0)
			fov_end = self.params.get("fov_end", None)
			batch_size = self.params.get("batch_size", 4)
			n_workers = self.params.get("n_workers", 4)

			success = self.workflow_coordinator.run_complete_workflow(
				self.nd2_path,
				self.data_info,
				self.output_dir,
				self.params,
				fov_start=fov_start,
				fov_end=fov_end,
				batch_size=batch_size,
				n_workers=n_workers,
			)

			if success:
				self.finished.emit(True, f"Results saved to {self.output_dir}")
			else:
				self.finished.emit(False, "Workflow failed")

		except Exception as e:
			self.finished.emit(False, f"Workflow error: {str(e)}")