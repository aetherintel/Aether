
import asyncio
import logging

# Configure logging to see details
logging.basicConfig(level=logging.INFO)

from services.text2cypher_service import Text2CypherService

async def run_test():
    print("🚀 Starting Internal Text2Cypher Test")
    
    try:
        service = Text2CypherService()
        
        # 1. Test Schema
        print("\n📊 Fetching Schema from MCP...")
        schema = await service.get_schema()
        print(f"✅ Schema received! ({len(schema)} chars)")
        print(f"Sample: {schema[:100]}...")
        
        # 2. Test Generation
        question = "What are the channels about?"
        print(f"\n🧠 Generating Cypher for: '{question}'")
        result = await service.run_text2cypher(question)
        
        print("\n🎉 Result:")
        print(f"Cypher: {result.get('cypher')}")
        print(f"Data: {result.get('results')}")
        
    except Exception as e:
        print(f"\n❌ FAST FAIL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
