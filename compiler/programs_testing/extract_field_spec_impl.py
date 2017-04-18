from dsl import *
from elements_library import *

KeyVal = create_state("KeyVal", "uint16_t keylen; uint16_t vallen; uint8_t key[keylen]; uint8_t val[vallen];")
MSG = create_state("Msg", "KeyVal kv;")

Forward = create_identity("Forward", "Msg*")
f = Forward()

p = create_element_instance("print",
              [Port("in_keylen", ["uint16_t"]), Port("in_key", ["uint8_t*"])],
              [],
               r'''
uint16_t keylen = in_keylen();
uint8_t* key = in_key();
for(int i=0; i<keylen; i++) printf("%d\n", key[i]);
''')

def spec(x):
    f = Forward()
    return f(x)

def impl(x):
    f = Forward()
    g = Forward()
    return g(f(x))

compo = create_spec_impl("compo", spec, impl)

x = compo(f(None))
p(x.get('kv').get('keylen'), x.get('kv.key'))

t = API_thread("get_key_val", ["Msg*"], None)
t.run_start(f, compo, p)

c = Compiler()
c.resource = False
c.remove_unused = False
c.desugar_mode = "impl"
c.testing = r'''
Msg* m = malloc(sizeof(Msg)+4);
m->kv.keylen = 2;
m->kv.vallen = 2;
uint16_t* key = (uint16_t*) m->kv._rest;
uint16_t* val = ((uint16_t*) m->kv._rest) + 1;
  *key = 11;
  *val = 7;

get_key_val(m);
'''
c.generate_code_and_run([11,0])