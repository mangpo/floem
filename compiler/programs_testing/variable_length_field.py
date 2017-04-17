from dsl import *

KeyVal = create_state("KeyValue", "uint16_t keylen; uint16_t vallen; uint8_t key[keylen]; uint8_t val[vallen];")


get_key_val = create_element_instance("get_key_val",
              [Port("in", ["KeyValue*"])],
              [Port("out", ["uint16_t", "uint8_t*", "uint16_t", "uint8_t*"])],
               r'''
KeyValue* m = in();
void* key = extract*(m, KeyValue, key); // m->key
void* val = extract*(m, KeyValue, val); // m->val
output { out(m->keylen, key, m->vallen, val); }
''')

p = create_element_instance("print",
              [Port("in", ["uint16_t", "uint8_t*", "uint16_t", "uint8_t*"])],
              [],
               r'''
(uint16_t keylen, uint8_t* key, uint16_t vallen, uint8_t* val) = in();
for(int i=0; i<keylen; i++) printf("%d\n", key[i]);
for(int i=0; i<vallen; i++) printf("%d\n", val[i]);
''')

p(get_key_val(None))

c = Compiler()
c.remove_unused = False
c.testing = r'''
KeyValue* m = malloc(sizeof(KeyValue)+4);
m->keylen = 2;
m->vallen = 2;
uint16_t* key = (uint16_t*) m->_rest;
uint16_t* val = ((uint16_t*) m->_rest) + 1;
  *key = 1;
  *val = 7;

get_key_val(m);
'''
c.generate_code_and_run([1,0,7,0])