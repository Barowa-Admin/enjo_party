# Copyright (c) 2026, Elia and contributors
# For license information, please see license.txt

_PATCHED = False


def apply_subscription_erpnext_patch():
    """Wrap ERPNext create_subscription_process so pause flag is respected."""
    global _PATCHED
    if _PATCHED:
        return

    from erpnext.accounts.doctype.process_subscription import process_subscription

    original = process_subscription.create_subscription_process

    def create_subscription_process_with_pause(subscription=None, posting_date=None):
        from enjo_party.enjo_party.utils.subscription_settings_helper import (
            is_subscription_automation_paused,
            log_subscription_automation_paused,
        )

        if is_subscription_automation_paused():
            log_subscription_automation_paused(
                f"ERPNext create_subscription_process übersprungen "
                f"(subscription={subscription}, posting_date={posting_date})"
            )
            return
        return original(subscription=subscription, posting_date=posting_date)

    process_subscription.create_subscription_process = create_subscription_process_with_pause
    _PATCHED = True
