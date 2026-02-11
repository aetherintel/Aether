
import re

def _build_cypher_mock(plan, schema=None):
    # Simplified mock of the relevant parts of _build_cypher_from_plan
    
    # ... (Node and Match logic omitted for brevity as they aren't the issue here) ...
    full_match = "MATCH (m:Message)"
    full_where = ""
    full_return = "RETURN m"

    # 6. Order/Limit
    order_by_val = plan.get('order_by')
    limit_val = plan.get('limit')
    
    node_map = {"m": "Message"} # Mock node map
    used_nodes = {"m"}
    
    order_by_clause = ""
    if order_by_val:
        order_by_str = str(order_by_val).strip()
        
        # --- PROPOSED FIX STARTS HERE ---
        
        # 1. Strip trailing LIMIT from order_by if present
        # Regex to find "LIMIT <number>" at the end, case insensitive
        limit_match = re.search(r'\s+(LIMIT\s+\d+)\s*$', order_by_str, re.IGNORECASE)
        if limit_match:
            print(f"DEBUG: Found LIMIT in ORDER BY: '{limit_match.group(1)}'. Stripping.")
            order_by_str = order_by_str[:limit_match.start()].strip()
            
        # 2. Fix Label.property -> variable.property
        # Regex for Label.Prop
        # We need to know valid labels? Or just assume Capitalized.Prop?
        # Let's try to match "Message.date"
        label_prop_match = re.match(r'^([A-Z][a-zA-Z0-9_]*)\.([a-zA-Z0-9_]+)', order_by_str)
        if label_prop_match:
            label = label_prop_match.group(1)
            prop = label_prop_match.group(2)
            print(f"DEBUG: Found Label.Prop: {label}.{prop}")
            
            # Find variable for label
            # detailed implementation would search node_map
            # Mock:
            found_var = None
            for var, l in node_map.items():
                if l == label:
                    found_var = var
                    break
            
            if found_var:
                 order_by_str = f"{found_var}.{prop} {order_by_str[len(label)+1+len(prop):]}"
                 print(f"DEBUG: Fixed to {order_by_str}")

        # --- FIX ENDS ---

        # Original logic (simplified)
        if "date" in order_by_str and "." not in order_by_str:
             # Find main variable
             main_var = "m"
             order_by_str = order_by_str.replace("date", f"{main_var}.date")

        if order_by_str.upper().startswith("ORDER BY"):
            order_by_clause = order_by_str
        else:
            order_by_clause = f"ORDER BY {order_by_str}"

    limit_clause = ""
    if limit_val is not None:
         limit_str = str(limit_val).strip()
         if limit_str.upper().startswith("LIMIT"):
             limit_clause = limit_str
         else:
             limit_clause = f"LIMIT {limit_str}"

    parts_final = [full_match, full_where, full_return, order_by_clause, limit_clause]
    return " ".join([p for p in parts_final if p])


# Test Case 1: Double LIMIT
plan1 = {
    "order_by": "date DESC LIMIT 100",
    "limit": 100
}
print(f"Test 1 (Double LIMIT): {_build_cypher_mock(plan1)}")

# Test Case 2: Label.Prop
plan2 = {
    "order_by": "Message.date DESC",
    "limit": 50
}
print(f"Test 2 (Label.Prop): {_build_cypher_mock(plan2)}")
