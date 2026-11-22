def account(rows, isolated, copies, headings, blanks, data_lines, pending=0):
    # pending 行同时计入 isolated（沿用隔离勾稽），accepted_total 不再重复加。
    categories = dict(rows=len(rows), isolated=len(isolated), copies=len(copies),
                      pending=pending, headings=headings, blanks=blanks)
    accepted_total = len(rows) + len(isolated) + len(copies) + headings + blanks - 1
    return dict(categories, data_lines=data_lines, balanced=accepted_total == data_lines)
