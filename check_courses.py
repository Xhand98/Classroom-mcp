#!/usr/bin/env python3
import asyncio
import json
from fastmcp import Client

async def check():
    print("🔍 Verificando cursos y tareas...\n")
    
    mcp = Client("main.py")
    
    async with mcp:
        # 1. Obtener cursos
        print("📚 Obteniendo cursos...")
        courses_result = await mcp.call_tool("getCourses", {})
        
        if hasattr(courses_result, 'content'):
            courses_data = json.loads(courses_result.content[0].text)
            print(f"✅ Cursos encontrados: {len(courses_data)}\n")
            
            for i, course in enumerate(courses_data[:10], 1):
                print(f"{i}. {course.get('name', 'Sin nombre')}")
                print(f"   ID: {course.get('id')}")
                print(f"   Profesor: {course.get('ownerId', 'N/A')}")
                print(f"   Estado: {course.get('courseState', 'N/A')}")
                print()
        
        # 2. Obtener todas las tareas
        print("\n📋 Obteniendo tareas...")
        tasks_result = await mcp.call_tool("get_tasks", {})
        
        if hasattr(tasks_result, 'content'):
            tasks_data = json.loads(tasks_result.content[0].text)
            print(f"✅ Tareas totales: {len(tasks_data)}\n")
            
            # Agrupar por courseId
            courses_count = {}
            for task in tasks_data:
                cid = task.get('courseId', 'unknown')
                courses_count[cid] = courses_count.get(cid, 0) + 1
            
            print("📊 Tareas por curso:")
            for cid, count in sorted(courses_count.items(), key=lambda x: x[1], reverse=True):
                print(f"   Curso {cid}: {count} tareas")

if __name__ == "__main__":
    asyncio.run(check())
