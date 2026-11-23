from sqlglot import exp

def is_table_volatile(tree):
    if not isinstance(tree, exp.Create):
        return False
    else:
        table_prop = tree.find(exp.StabilityProperty)
        if table_prop is None:
            return False
        if table_prop.name.upper() == "VOLATILE":
            return True
        else:
            return False

def full_name(table):
    if table.db:
        return f"{table.db}.{table.name}"
    else:
        return table.name

def get_table_lineage (tree,temp_tables):
    WRITE_TYPES=(
        exp.Create,
        exp.Insert,
        exp.Update,
        exp.Merge 
    )
    if isinstance(tree, WRITE_TYPES):
        print("yes it is write statement. It belongs CTAS,insert, update, merge")
    else:
        print("Lineage cannot be determined")
        return None

    first_level = tree.this
    if isinstance(first_level, exp.Table):
        target_table_node = first_level
    elif isinstance(first_level,exp.Schema) and isinstance(first_level.this, exp.Table):
         target_table_node = first_level.this
    else:
        print("target cannot be determined")
        return None
    print("-----start-----")
    print(f"target db={target_table_node.db} target table = {target_table_node.name}")
    sources = []
    for node in tree.find_all(exp.Table):
        if node is not target_table_node:
            print(f"source db={node.db} souce table name={node.name}")
            temp_src_list = temp_tables.get(full_name(node))
            print("temp_src_list type ",type(temp_src_list),"temp_src_list",temp_src_list)
            if temp_src_list is not None:
                print("inside if before extend ",temp_src_list)
                sources.extend(temp_src_list)               
            else:
                sources.append(full_name(node))
    
    if is_table_volatile(tree):        
        temp_tables[full_name(target_table_node)] =sources
        print("inside is table volatile",temp_tables)
        return None  
    print("-----end-----")
    return (full_name(target_table_node), sources)

