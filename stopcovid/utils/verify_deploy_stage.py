import os


def verify_deploy_stage():
    stage = os.environ["STAGE"]
    deploy_stage = os.getenv("DEPLOY_STAGE")
    if stage != deploy_stage:
        raise EnvironmentError(
            f"There is a mismatch between your stage and environment variables. "
            f"Exiting. (STAGE={stage}, DEPLOY_STAGE={deploy_stage})"
        )
