
import asyncio
import os
import sys

# Ensure backend directory is in pythonpath
sys.path.append(os.path.abspath("backend/app"))

from services.text2cypher_service import Text2CypherService

async def test_text2cypher():
    print("Testing Text2Cypher integration...")
    service = Text2CypherService()
    
    # 1. Test Schema Retrieval
    print("\n1. Testing Schema Retrieval...")
    try:
        schema = await service.get_schema()
        print(f"✅ Schema retrieved! Length: {len(schema)} chars")
        print(f"Schema Snippet: {schema[:200]}...")
    except Exception as e:
        print(f"❌ Schema Retrieval Failed: {e}")
        return

    # 2. Test End-to-End Query
    question = "How many messages are there in total?"
    print(f"\n2. Testing Query Generation & Execution for: '{question}'")
    
    try:
        result = await service.run_text2cypher(question)
        print("\n✅ Execution Successful!")
        print(f"Cypher Query: {result.get('cypher')}")
        print(f"Results: {result.get('results')}")
        print(f"Time: {result.get('generation_metrics', {}).get('time')}s")
        
        if result.get("error"):
            print(f"⚠️ Partial Execution Error: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Execution Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_text2cypher())
