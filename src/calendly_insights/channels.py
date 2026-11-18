"""Which marketing channel a Calendly booking belongs to.

The channel is identified by the booking's event type (payload.scheduled_event.event_type).
Only these three event types are marketing bookings; anything else is not marketing.
"""

EVENT_TYPE_TO_CHANNEL = {
    "https://api.calendly.com/event_types/79652b8a-1688-4d0b-ba8f-733c70856de4": "facebook_paid_ads",
    "https://api.calendly.com/event_types/2b5580c2-13e9-4283-8b4d-56401cf31554": "youtube_paid_ads",
    "https://api.calendly.com/event_types/70022cde-e64f-49a0-9362-a815186005dc": "tiktok_paid_ads",
}


def channel_for_event_type(event_type_uri: str | None) -> str | None:
    """Return the channel name for an event type URI, or None if it is not a marketing event type."""
    if event_type_uri is None:
        return None
    return EVENT_TYPE_TO_CHANNEL.get(event_type_uri.strip())
