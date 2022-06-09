import logging
from html import escape as escape_html
from traceback import format_exc
from datetime import timedelta

import anyio


from ..commands import (
    RESET_DEVICE_STATUS_MAP,
    SET_ELECTRONICS_REFERENCE_STATUS_MAP,
    reset_device,
    set_electronics_reference,
)
from ..device import Device
from ..progress import ProgressManager, StatusMap, StatusStream, Idle
from .models import RunPlan
from .widgets._outcome_widget import OutcomeWidget

_LOGGER = logging.getLogger()  # root logger

_CHECK_SIGNAL_INTEGRITY_STATUS_MAP: StatusMap = {
    "check_signal_integrity": Idle(expected_duration=timedelta(seconds=1), tries=0),
}


async def start_run(
    run_plan: RunPlan,
    progress_send_stream: StatusStream,
    cancel_scope: anyio.CancelScope,
    outcome_widget: OutcomeWidget,
) -> None:
    async with progress_send_stream:
        with cancel_scope:
            try:
                # Early out if already cancelled.
                # TODO: Check if anyio fixed this issue upstream:
                #
                #     https://github.com/agronholm/anyio/issues/433
                #
                if cancel_scope.cancel_called:
                    raise anyio.get_cancelled_exc_class()()

                reset_params = run_plan.parameters.reset_params
                reset_device_settings = run_plan.steps.reset_device_settings

                # Progress manager
                status_map: StatusMap = {
                    **RESET_DEVICE_STATUS_MAP,
                    **SET_ELECTRONICS_REFERENCE_STATUS_MAP,
                    **_CHECK_SIGNAL_INTEGRITY_STATUS_MAP,
                }

                progress_manager = ProgressManager(
                    status_map, status_stream=progress_send_stream
                )

                # Device and it's description
                device = Device.from_description(
                    reset_params.device_description, logger=_LOGGER
                )
                async with device, progress_manager:
                    await reset_device(
                        device,
                        reset_params.swu_file,
                        reset_params.branding,
                        settings=reset_device_settings,
                        progress_manager=progress_manager,
                        logger=_LOGGER,
                    )
                    if run_plan.steps.set_electronics_reference:
                        elec_ref = await set_electronics_reference(
                            device,
                            progress_manager=progress_manager,
                            settings=run_plan.steps.set_electronics_reference_settings,
                            logger=_LOGGER,
                        )
                        assert (
                            elec_ref is not None
                        ), "When the step is enabled, we get a result"
                        outcome_widget.setElecRef(elec_ref)

                        # Test the reference frequencies
                        if run_plan.steps.check_signal_integrity:
                            async with progress_manager.step("check_signal_integrity"):
                                if not elec_ref.is_accepted:
                                    raise RuntimeError(
                                        "Electronics do not pass the signal integrity test."
                                    )
            except anyio.get_cancelled_exc_class():
                message = "User cancelled"
                background = "grey"
            # Catch broad `Exception` as we want to handle all the general errors
            except (  # pylint: disable=broad-except
                anyio.ExceptionGroup,
                Exception,
            ):
                message = format_exc()
                background = "red"
            else:
                message = "Done"
                background = "green"
    style = f"color: white; background-color: {background};"
    # We add line breaks to make the message stand out
    message_html = escape_html(message)
    html = f'<pre style="{style}">{message_html}</pre>'
    outcome_widget.appendLogHtml(html)
