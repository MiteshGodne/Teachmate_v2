class PipelineError(Exception):
    """An error whose message is safe to show to the end user."""


class JobCancelled(Exception):
    """Raised inside the pipeline when the user cancelled the job."""