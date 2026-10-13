from .avatar import (
    router,
    upload_user_avatar,
    remove_user_avatar,
    update_avatar_color,
)
from .avatar.schemas import AvatarColorRequest
from .avatar.constants import (
    ALLOWED_IMAGE_TYPES,
    MAX_AVATAR_SIZE_BYTES,
    VALID_AVATAR_COLORS,
)

__all__ = [
    "router",
    "upload_user_avatar",
    "remove_user_avatar",
    "update_avatar_color",
    "AvatarColorRequest",
    "ALLOWED_IMAGE_TYPES",
    "MAX_AVATAR_SIZE_BYTES",
    "VALID_AVATAR_COLORS",
]
