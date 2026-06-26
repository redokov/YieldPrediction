from mcp.server.fastmcp import FastMCP
from .search import list_scenes, create_buffer
from .processor import process_scene
from .llm import call_llm
from .models import SearchRequest

mcp = FastMCP("rlm")


@mcp.tool()
def list_available_scenes(kml_path: str, start_date: str = "2024-04-01", end_date: str = "2024-09-30", max_cloud_cover: int = 30):
    """Поиск доступных малооблачных сцен Sentinel-2 для поля"""
    request = SearchRequest(
        kml_path=kml_path,
        start_date=start_date,
        end_date=end_date,
        max_cloud_cover=max_cloud_cover
    )
    scenes = list_scenes(request)
    return {
        "scenes_found": len(scenes),
        "scenes": [s.model_dump() for s in scenes[:10]]  # возвращаем до 10 сцен
    }


@mcp.tool()
def analyze_field(kml_path: str, use_llm: bool = True):
    """Полный анализ поля с буфером 500м и LLM"""
    result = process_scene(kml_path=kml_path)
    
    if use_llm and result.report:
        llm_analysis = call_llm(
            prompt=f"Проанализируй агрономический отчёт и дай рекомендации:\n\n{result.report}",
            system_prompt="Ты — опытный агроном. Давай точные практические рекомендации по состоянию поля.",
            temperature=0.3
        )
        result.llm_analysis = llm_analysis
        result.report += f"\n\n=== Анализ от Qwen3 (OpenRouter) ===\n{llm_analysis}"
    
    return result.model_dump()

def main():
    """Запуск MCP сервера RLM"""
    print("🚀 Запуск RLM MCP Server (Qwen3 via OpenRouter)...")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
