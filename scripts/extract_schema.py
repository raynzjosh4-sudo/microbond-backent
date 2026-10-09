import marshal, types

def get_strings(c):
    s = [x for x in c.co_consts if isinstance(x, str)]
    for x in c.co_consts:
        if isinstance(x, types.CodeType):
            s.extend(get_strings(x))
    return s

with open(r'app\schemas\__pycache__\group_settings_update_request.cpython-313.pyc', 'rb') as f:
    f.read(16)
    print(get_strings(marshal.load(f)))
