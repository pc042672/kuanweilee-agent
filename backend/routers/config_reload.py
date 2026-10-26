"""FastAPI router for configuration reload endpoint."""

from fastapi import APIRouter, Depends

from backend.auth import require_admin
from backend.config import get_config_manager

router = APIRouter(prefix="/api/config", tags=["config"], dependencies=[Depends(require_admin)])


@router.post("/reload")
async def reload_config():
    """Reload configuration files without restarting the server."""
    config = get_config_manager()
    config.reload()
    try:
        ontology = config.load_ontology()
        return {
            "status": "success",
            "message": "Configuration reloaded successfully",
            "ontology_version": ontology.version,
            "node_count": len(ontology.nodes),
            "note": "Restart server for agents to use new configuration",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
