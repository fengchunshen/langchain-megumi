# mypy: disable - error - code = "no-untyped-def,misc"
import pathlib
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

# Define the FastAPI app
app = FastAPI()


class QueryConfirmationRequest(BaseModel):
    """用户查询确认请求"""
    thread_id: str
    action: str  # 'confirm', 'modify', or 'cancel'
    queries: List[str]  # 确认或修改后的查询


@app.post("/user-confirmation")
async def handle_user_confirmation(request: QueryConfirmationRequest):
    """处理用户对生成查询的确认或修改"""
    try:
        # 这里应该更新对应thread的状态
        # 由于LangGraph的特性，我们需要通过状态更新来继续流程
        
        # 返回确认结果
        return {
            "status": "success",
            "message": "用户确认已接收",
            "action": request.action,
            "queries": request.queries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def create_frontend_router(build_dir="../frontend/dist"):
    """Creates a router to serve the React frontend.

    Args:
        build_dir: Path to the React build directory relative to this file.

    Returns:
        A Starlette application serving the frontend.
    """
    build_path = pathlib.Path(__file__).parent.parent.parent / build_dir

    if not build_path.is_dir() or not (build_path / "index.html").is_file():
        print(
            f"WARN: Frontend build directory not found or incomplete at {build_path}. Serving frontend will likely fail."
        )
        # Return a dummy router if build isn't ready
        from starlette.routing import Route

        async def dummy_frontend(request):
            return Response(
                "Frontend not built. Run 'npm run build' in the frontend directory.",
                media_type="text/plain",
                status_code=503,
            )

        return Route("/{path:path}", endpoint=dummy_frontend)

    return StaticFiles(directory=build_path, html=True)


# Mount the frontend under /app to not conflict with the LangGraph API routes
app.mount(
    "/app",
    create_frontend_router(),
    name="frontend",
)
