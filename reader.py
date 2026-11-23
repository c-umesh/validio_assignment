def read_sql_statements(file_path):
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