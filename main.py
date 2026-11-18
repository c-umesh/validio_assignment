import sqlglot
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
    elif isinstance(first_level.this, exp.Table):
         target_table_node = first_level.this
    else:
        print("target cannot be determined")
        return None
    print(f"target db={target_table_node.db} target table = {target_table_node.name}")
    sources = []
    for node in tree.find_all(exp.Table):
        if node is not target_table_node:
            print(f"source db={node.db} souce table name={node.name}")
            temp_src_list = temp_tables.get(full_name(node))
            if temp_src_list is not None:
                sources.extend(temp_src_list)
            else:
                sources.append(full_name(node))
    
    if is_table_volatile(tree):        
        temp_tables[full_name(target_table_node)] =sources
        print("inside is table volatile",temp_tables)
        return None  

    return (full_name(target_table_node), sources)

def read_sql_statemets(file_path):
    with open(file_path,"r",encoding="utf-8") as f:
        sql_text = f.read()

    sql_statements=[]
    for sql_stmt in sql_text.split(";"):
        lines =[]
        for line in sql_stmt.splitlines():
            sql_ln= line.strip()
            if not sql_ln.startswith("--"):
                lines.append(sql_ln)

        sql = "\n".join(lines).strip()
        if sql:
            sql_statements.append(sql)
    return sql_statements

def main():
    lineage=[]
    temp_tables={}
    file_path = "data/query_log.sql"
    sql_statements=read_sql_statemets(file_path)
    i=1
    for sql in sql_statements:
        if sql.strip().upper().startswith(("EXEC ", "EXECUTE ", "CALL ")):
            print("FLAG: macro/procedure call, lineage not recoverable from log text")
            continue
        tree = sqlglot.parse_one(sql, read="teradata")   # SQL text → tree
        print(f"printing source and target tables for sql{i}")
        result_set=get_table_lineage(tree,temp_tables)
        if result_set is None:  # nothing to unpack handle scenario without target ,or plain select.
            continue
        target_db_tbl, source_db_tbl=result_set
        lineage.append((target_db_tbl, source_db_tbl))
        i= i+1

    print("temp tables")
    print(temp_tables)
    print("printing lineage")
    for target, sources in lineage:
        print(f"{target} -> {sources}") 


if __name__ == "__main__":
    main()