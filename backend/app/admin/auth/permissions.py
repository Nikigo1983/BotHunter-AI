from app.models.enums import DashboardRole

PERMISSION_VIEW = "view"
PERMISSION_MODERATE = "moderate"
PERMISSION_MANAGE_CHANNELS = "manage_channels"
PERMISSION_CHANGE_AI_SETTINGS = "change_ai_settings"
PERMISSION_CHANGE_SYSTEM_SETTINGS = "change_system_settings"
PERMISSION_MANAGE_BACKUP = "manage_backup"
PERMISSION_VIEW_SECRETS = "view_secrets"
PERMISSION_MANAGE_USERS = "manage_users"

_ROLE_PERMISSIONS: dict[DashboardRole, set[str]] = {
    DashboardRole.OWNER: {
        PERMISSION_VIEW,
        PERMISSION_MODERATE,
        PERMISSION_MANAGE_CHANNELS,
        PERMISSION_CHANGE_AI_SETTINGS,
        PERMISSION_CHANGE_SYSTEM_SETTINGS,
        PERMISSION_MANAGE_BACKUP,
        PERMISSION_VIEW_SECRETS,
        PERMISSION_MANAGE_USERS,
    },
    DashboardRole.ADMINISTRATOR: {
        PERMISSION_VIEW,
        PERMISSION_MODERATE,
        PERMISSION_MANAGE_CHANNELS,
        PERMISSION_CHANGE_AI_SETTINGS,
        PERMISSION_CHANGE_SYSTEM_SETTINGS,
        PERMISSION_MANAGE_BACKUP,
        PERMISSION_VIEW_SECRETS,
    },
    DashboardRole.MODERATOR: {
        PERMISSION_VIEW,
        PERMISSION_MODERATE,
        PERMISSION_MANAGE_CHANNELS,
    },
    DashboardRole.VIEWER: {
        PERMISSION_VIEW,
    },
}


def parse_role(role: str) -> DashboardRole:
    try:
        return DashboardRole(role)
    except ValueError:
        return DashboardRole.VIEWER


def has_permission(role: str, permission: str) -> bool:
    parsed = parse_role(role)
    return permission in _ROLE_PERMISSIONS.get(parsed, set())


def role_label(role: str) -> str:
    labels = {
        DashboardRole.OWNER.value: "Owner",
        DashboardRole.ADMINISTRATOR.value: "Administrator",
        DashboardRole.MODERATOR.value: "Moderator",
        DashboardRole.VIEWER.value: "Viewer",
    }
    return labels.get(role, role)
