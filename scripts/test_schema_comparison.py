#!/usr/bin/env python3
"""
Test script to compare the old vs new schema that the LLM sees
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "app"))

from services.text2cypher_service import Text2CypherService
from dotenv import load_dotenv

# Load environment
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env.dev')


async def main():
    print("🔍 Fetching schema from Neo4j MCP...")
    print("="*80)

    service = Text2CypherService()

    try:
        schema_text, schema_json = await service.get_schema()

        print("\n✅ Schema successfully fetched!")
        print(f"\n📊 Statistics:")
        print(f"   Schema text length: {len(schema_text)} characters")
        print(f"   Estimated tokens: ~{len(schema_text.split())} tokens")

        # Count nodes and relationships
        node_count = schema_text.count("- Message") + schema_text.count("- Channel") + \
                    schema_text.count("- User") + schema_text.count("- Location") + \
                    schema_text.count("- Emotion") + schema_text.count("- Classification")

        rel_count = schema_text.count(")-[:")

        print(f"   Visible node types: {node_count}")
        print(f"   Visible relationships: {rel_count}")

        print("\n" + "="*80)
        print("FULL SCHEMA TEXT (what the LLM sees):")
        print("="*80)
        print(schema_text)
        print("="*80)

        # Show what properties are on Message node
        if "Message" in schema_json:
            msg_props = list(schema_json["Message"].get("properties", {}).keys())
            print(f"\n📋 Message node has {len(msg_props)} total properties in Neo4j:")
            print(f"   {', '.join(sorted(msg_props))}")

            # Check which are shown
            shown_props = []
            for prop in msg_props:
                if prop in schema_text:
                    shown_props.append(prop)

            print(f"\n✅ Showing {len(shown_props)} simplified properties to LLM")
            print(f"❌ Hiding {len(msg_props) - len(shown_props)} legacy properties")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
