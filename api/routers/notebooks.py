from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from api.models import NotebookCreate, NotebookResponse, NotebookUpdate
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


@router.get("/notebooks", response_model=List[NotebookResponse])
async def get_notebooks(
    request: Request,
    archived: Optional[bool] = Query(None, description="Filter by archived status"),
    order_by: str = Query("updated desc", description="Order by field and direction"),
):
    """Get all notebooks with optional filtering and ordering."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        # Build the query with counts and user filter
        if user_id:
            # Multiuser mode - filter by user
            query = f"""
                SELECT *,
                count(<-reference.in) as source_count,
                count(<-artifact.in) as note_count
                FROM notebook
                WHERE user = $user_id
                ORDER BY {order_by}
            """
            result = await repo_query(query, {"user_id": ensure_record_id(user_id)})
        else:
            # Single-user mode (backward compatibility) - show all notebooks
            query = f"""
                SELECT *,
                count(<-reference.in) as source_count,
                count(<-artifact.in) as note_count
                FROM notebook
                ORDER BY {order_by}
            """
            result = await repo_query(query)

        # Filter by archived status if specified
        if archived is not None:
            result = [nb for nb in result if nb.get("archived") == archived]

        return [
            NotebookResponse(
                id=str(nb.get("id", "")),
                name=nb.get("name", ""),
                description=nb.get("description", ""),
                archived=nb.get("archived", False),
                created=str(nb.get("created", "")),
                updated=str(nb.get("updated", "")),
                source_count=nb.get("source_count", 0),
                note_count=nb.get("note_count", 0),
            )
            for nb in result
        ]
    except Exception as e:
        logger.error(f"Error fetching notebooks: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching notebooks: {str(e)}"
        )


@router.post("/notebooks", response_model=NotebookResponse)
async def create_notebook(request: Request, notebook: NotebookCreate):
    """Create a new notebook."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        new_notebook = Notebook(
            name=notebook.name,
            description=notebook.description,
            user=user_id,  # Assign to current user
        )
        await new_notebook.save()

        return NotebookResponse(
            id=new_notebook.id or "",
            name=new_notebook.name,
            description=new_notebook.description,
            archived=new_notebook.archived or False,
            created=str(new_notebook.created),
            updated=str(new_notebook.updated),
            source_count=0,  # New notebook has no sources
            note_count=0,  # New notebook has no notes
        )
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating notebook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error creating notebook: {str(e)}"
        )


@router.get("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(request: Request, notebook_id: str):
    """Get a specific notebook by ID."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        # Query with counts for single notebook
        query = """
            SELECT *,
            count(<-reference.in) as source_count,
            count(<-artifact.in) as note_count
            FROM $notebook_id
        """
        result = await repo_query(query, {"notebook_id": ensure_record_id(notebook_id)})

        if not result:
            raise HTTPException(status_code=404, detail="Notebook not found")

        nb = result[0]
        
        # Check user access (only in multiuser mode)
        if user_id:
            notebook_user = nb.get("user")
            # Convert notebook_user to string if it's a RecordID
            notebook_user_str = str(notebook_user) if notebook_user else None
            if notebook_user_str and notebook_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return NotebookResponse(
            id=str(nb.get("id", "")),
            name=nb.get("name", ""),
            description=nb.get("description", ""),
            archived=nb.get("archived", False),
            created=str(nb.get("created", "")),
            updated=str(nb.get("updated", "")),
            source_count=nb.get("source_count", 0),
            note_count=nb.get("note_count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching notebook: {str(e)}"
        )


@router.put("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(request: Request, notebook_id: str, notebook_update: NotebookUpdate):
    """Update a notebook."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        # Check user access (only in multiuser mode)
        if user_id:
            notebook_user_str = str(notebook.user) if notebook.user else None
            if notebook_user_str and notebook_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

        # Update only provided fields
        if notebook_update.name is not None:
            notebook.name = notebook_update.name
        if notebook_update.description is not None:
            notebook.description = notebook_update.description
        if notebook_update.archived is not None:
            notebook.archived = notebook_update.archived

        await notebook.save()

        # Query with counts after update
        query = """
            SELECT *,
            count(<-reference.in) as source_count,
            count(<-artifact.in) as note_count
            FROM $notebook_id
        """
        result = await repo_query(query, {"notebook_id": ensure_record_id(notebook_id)})

        if result:
            nb = result[0]
            return NotebookResponse(
                id=str(nb.get("id", "")),
                name=nb.get("name", ""),
                description=nb.get("description", ""),
                archived=nb.get("archived", False),
                created=str(nb.get("created", "")),
                updated=str(nb.get("updated", "")),
                source_count=nb.get("source_count", 0),
                note_count=nb.get("note_count", 0),
            )

        # Fallback if query fails
        return NotebookResponse(
            id=notebook.id or "",
            name=notebook.name,
            description=notebook.description,
            archived=notebook.archived or False,
            created=str(notebook.created),
            updated=str(notebook.updated),
            source_count=0,
            note_count=0,
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error updating notebook: {str(e)}"
        )


@router.post("/notebooks/{notebook_id}/sources/{source_id}")
async def add_source_to_notebook(request: Request, notebook_id: str, source_id: str):
    """Add an existing source to a notebook (create the reference)."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        # Check if notebook exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        # Check user access to notebook (only in multiuser mode)
        if user_id:
            notebook_user_str = str(notebook.user) if notebook.user else None
            if notebook_user_str and notebook_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied to notebook")

        # Check if source exists
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Check user access to source (only in multiuser mode)
        if user_id:
            source_user_str = str(source.user) if source.user else None
            if source_user_str and source_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied to source")

        # Check if reference already exists (idempotency)
        existing_ref = await repo_query(
            "SELECT * FROM reference WHERE out = $source_id AND in = $notebook_id",
            {
                "notebook_id": ensure_record_id(notebook_id),
                "source_id": ensure_record_id(source_id),
            },
        )

        # If reference doesn't exist, create it
        if not existing_ref:
            await repo_query(
                "RELATE $source_id->reference->$notebook_id",
                {
                    "notebook_id": ensure_record_id(notebook_id),
                    "source_id": ensure_record_id(source_id),
                },
            )

        return {"message": "Source linked to notebook successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error linking source {source_id} to notebook {notebook_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error linking source to notebook: {str(e)}"
        )


@router.delete("/notebooks/{notebook_id}/sources/{source_id}")
async def remove_source_from_notebook(request: Request, notebook_id: str, source_id: str):
    """Remove a source from a notebook (delete the reference)."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        # Check if notebook exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        # Check user access to notebook (only in multiuser mode)
        if user_id:
            notebook_user_str = str(notebook.user) if notebook.user else None
            if notebook_user_str and notebook_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

        # Delete the reference record linking source to notebook
        await repo_query(
            "DELETE FROM reference WHERE out = $notebook_id AND in = $source_id",
            {
                "notebook_id": ensure_record_id(notebook_id),
                "source_id": ensure_record_id(source_id),
            },
        )

        return {"message": "Source removed from notebook successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error removing source {source_id} from notebook {notebook_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error removing source from notebook: {str(e)}"
        )


@router.delete("/notebooks/{notebook_id}")
async def delete_notebook(request: Request, notebook_id: str):
    """Delete a notebook."""
    try:
        # Get user from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        # Check user access (only in multiuser mode)
        if user_id:
            notebook_user_str = str(notebook.user) if notebook.user else None
            if notebook_user_str and notebook_user_str != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

        await notebook.delete()

        return {"message": "Notebook deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting notebook: {str(e)}"
        )
