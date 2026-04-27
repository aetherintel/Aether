# neo4j_backend_client.py (Facade for repositories)

from repository.neo4j.base import (
    driver,
    get_session,
    close,
    convert_neo4j_datetime
)

from repository.neo4j.message_repo import (
    get_unified_timeline_messages,
    get_messages_by_id,
    get_messages_for_channel,
    get_user_messages,
    get_messages_with_media,
    get_total_message_count_for_channels,
    get_message_volume_over_time
)

from repository.neo4j.channel_repo import (
    get_channel_list,
    get_channel_by_id,
    get_user_channels,
    get_channel_locations_data,
    get_channel_emotions,
    get_active_channels_in_period
)

from repository.neo4j.graph_repo import (
    get_case_channels_with_recommendations,
    get_channel_recommendation_graph,
    get_user_interaction_graph,
    get_top_locations,
    get_aggregated_emotions
)
