from calendly_insights.channels import channel_for_event_type

FACEBOOK = "https://api.calendly.com/event_types/79652b8a-1688-4d0b-ba8f-733c70856de4"
YOUTUBE = "https://api.calendly.com/event_types/2b5580c2-13e9-4283-8b4d-56401cf31554"
TIKTOK = "https://api.calendly.com/event_types/70022cde-e64f-49a0-9362-a815186005dc"

# The event type in the requirements' sample webhook ("Data Engineer Academy Info Session"):
# a real booking, but not a marketing one.
INFO_SESSION = "https://api.calendly.com/event_types/d639ecd3-8718-4068-955a-436b10d72c78"


def test_three_marketing_event_types_map_to_their_channel():
    assert channel_for_event_type(FACEBOOK) == "facebook_paid_ads"
    assert channel_for_event_type(YOUTUBE) == "youtube_paid_ads"
    assert channel_for_event_type(TIKTOK) == "tiktok_paid_ads"


def test_other_event_type_is_not_marketing():
    assert channel_for_event_type(INFO_SESSION) is None


def test_missing_event_type_is_not_marketing():
    assert channel_for_event_type(None) is None


def test_surrounding_spaces_are_ignored():
    assert channel_for_event_type(f"  {TIKTOK}\n") == "tiktok_paid_ads"
