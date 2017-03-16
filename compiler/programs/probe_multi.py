from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Inject = create_inject("inject", "int", 10, "gen_func")
Probe = create_probe("probe", "int", 10, "cmp_func")
Drop = create_drop("Drop", "int")
Chioce = create_element("Choice",
            [Port("in", ["int"])],
            [Port("out1", ["int"]), Port("out2", ["int"])],
            r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')

inject = Inject()
f1 = Forward("f1")
f2 = Forward("f2")
drop = Drop()

def spec():
    probe = Probe()
    drop(probe(f2(f1(inject()))))


def impl():
    probe1 = Probe()
    probe2 = Probe()
    choice = Chioce()
    x1, x2 = choice(inject())
    drop(probe1(f1(x1)))
    drop(probe2(f2(x2)))

compo = create_spec_impl("compo", spec, impl)

t = internal_thread("t")
t.run(compo)
t.start(inject)

c = Compiler()
c.include = r'''
int gen_func(int i) { return i; }
void cmp_func(int spec_n, int *spec_data, int impl_n, int *impl_data) {
  if(!(spec_n == impl_n)) {
    printf("Spec records %d entries, but Impl records %d entries.\n", spec_n, impl_n);
    exit(-1);
  }
  for(int i=0; i<spec_n; i++) {
    if(!(*spec_data == *impl_data)) {
      printf("Spec[%d] = %d,  Impl[%d] = %d\n", i, *spec_data, i, *impl_data);
      exit(-1);
    }
    spec_data++;
    impl_data++;
  }
  printf("PASSED: n = %d\n", spec_n);
}
'''
c.testing = r'''
spec_run_threads();
usleep(1000);
spec_kill_threads();
impl_run_threads();
usleep(1000);
impl_kill_threads();
'''
c.desugar_mode = "compare"
c.generate_code_and_run()