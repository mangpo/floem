from dsl import *
from elements_library import *

table_put, table_get = create_table_instances("table_put", "table_get", "int", "int", 64)

put = create_element_instance("put",
            [Port("in", ["int", "int"])],
            [Port("out_index", ["int"]), Port("out_value", ["int"])],
            r'''(int key, int val) = in(); output { out_index(key); out_value(val); }''')

key, val = put(None)
table_put(key,val)

val_out = table_get(None)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = "put(1,111); put(2,222); table_get(2); table_get(1);"
c.generate_code_and_run([222,111])
