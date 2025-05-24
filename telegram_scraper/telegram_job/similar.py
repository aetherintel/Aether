from telethon import functions, types
from telegram_job.telegram_client import client
from telethon.errors.rpcerrorlist import UsernameInvalidError

async def similar_channels(username: str):
    entity = await client.get_input_entity(username)
    if not isinstance(entity, (types.InputChannel, types.InputPeerChannel)):
        raise ValueError("not a channel")

    input_ch = types.InputChannel(entity.channel_id, entity.access_hash)
    rec = await client(functions.channels.GetChannelRecommendationsRequest(
        channel=input_ch))
    print(rec)
    print(input_ch)
    return [{"username": ch.username, "title": ch.title, "id": ch.id}
            for ch in rec.chats if getattr(ch, "username", None)]

async def _search_fallback(query: str, limit: int = 15):
    """Use contacts.search as a best-effort fallback."""
    res = await client(functions.contacts.SearchRequest(q=query, limit=limit))
    chans = [
        {"username": ch.username, "title": ch.title, "id": ch.id}
        for ch in res.chats
        if isinstance(ch, types.Channel) and ch.username
    ]
    return chans

async def similar_channels_flexible(user_input: str, limit: int = 15):
    # 1️⃣ ensure client is connected
    from .telegram_client import login
    await login()

    # 2️⃣ try the “official” recommendations API
    try:
        recs = await similar_channels(user_input)
        if recs:
            return recs
    except UsernameInvalidError:
        # treat as “no recs”
        pass

    # 3️⃣ fall back to keyword search
    return await _search_fallback(user_input, limit)
