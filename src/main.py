"""Main application entry point for MeetHub background service."""

import asyncio

import sys

from pathlib import Path



from src.config import settings

from src.services.scheduler import SchedulerService

from src.utils.logging import get_logger, setup_logging



logger = get_logger(__name__)





async def main() -> int:

    """Main application entry point.



    Returns:

        Exit code (0 for success, 1 for error)

    """

    # Setup logging

    setup_logging()



    logger.info(

        "MeetHub starting",

        app_name=settings.app_name,

        environment=settings.environment,

        poll_interval_minutes=settings.poll_interval_minutes,

        max_concurrent_jobs=settings.max_concurrent_jobs,

    )



    # Validate critical configuration

    if not _validate_configuration():

        logger.error("Configuration validation failed, exiting")

        return 1



    # Initialize scheduler service

    try:

        scheduler = SchedulerService()

        scheduler.start()



        logger.info("MeetHub background service started successfully")



        # Run forever (until signal received)

        await scheduler.run_forever()



        logger.info("MeetHub shutting down gracefully")

        return 0



    except KeyboardInterrupt:

        logger.info("Received keyboard interrupt, shutting down")

        return 0



    except Exception as e:

        logger.error(

            "Fatal error in main application",

            error=str(e),

            error_type=type(e).__name__,

        )

        return 1





def _validate_configuration() -> bool:

    """Validate critical configuration before starting.



    Returns:

        True if configuration is valid, False otherwise

    """

    errors = []



    # Validate auth mode specific requirements

    if settings.is_service_account_mode:

        # Service account mode validation

        if not settings.google_service_account_path.exists():

            errors.append(

                f"Service account file not found: {settings.google_service_account_path}"

            )



        if not settings.google_workspace_admin_email:

            errors.append(

                "GOOGLE_WORKSPACE_ADMIN_EMAIL not configured (required for service account mode)"

            )



    elif settings.is_personal_mode:

        # OAuth mode validation

        if not settings.google_oauth_credentials_path.exists():

            errors.append(

                f"OAuth credentials file not found: {settings.google_oauth_credentials_path}. "

                f"Download from Google Cloud Console and save as credentials.json"

            )



        logger.info(

            "Running in Personal Mode (OAuth)",

            note="Only your own meetings will be processed. First run will require browser authentication.",

        )



    # Common validations

    if not settings.deepgram_api_key:

        errors.append("DEEPGRAM_API_KEY not configured")



    if not settings.drive_root_folder_id:

        errors.append("DRIVE_ROOT_FOLDER_ID not configured")



    # Log errors

    if errors:

        logger.error(

            "Configuration validation failed",

            auth_mode=settings.google_auth_mode,

            errors=errors,

        )

        for error in errors:

            logger.error(f"  - {error}")

        return False



    logger.info(

        "Configuration validation passed",

        auth_mode=settings.google_auth_mode,

    )

    return True





if __name__ == "__main__":

    exit_code = asyncio.run(main())

    sys.exit(exit_code)
