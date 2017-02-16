from compiler import *
from standard_elements import *
from desugaring import desugar

(t_state, t_insert_element, t_get_element, t_state_instance, t_insert_instance, t_get_instance) = \
    get_table_collection("int", "int", 64, "msg_put", "msg_get")

p = Program(
    t_state, t_insert_element, t_get_element, t_state_instance, t_insert_instance, t_get_instance,
    Element("Put",
            [Port("in", ["int", "int"])],
            [Port("out_index", ["int"]), Port("out_value", ["int"])],
            r'''(int key, int val) = in(); output { out_index(key); out_value(val); }'''),
    ElementInstance("Put", "put"),
    Connect("put", "msg_put", "out_index", "in_index"),
    Connect("put", "msg_put", "out_value", "in_value")
)

g = generate_graph(desugar(p))
generate_code_and_run(g, "put(1,111); put(2,222); msg_get(2); msg_get(1);", [222,111])