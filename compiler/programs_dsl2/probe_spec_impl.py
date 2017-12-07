from library_dsl2 import *
from compiler import Compiler

Inject = create_inject("inject", "int", 10, "gen_func")
Probe = create_probe("probe", "int", 10, "cmp_func")

inject = Inject()
probe = Probe()
f = Identity(configure=[Int])
g = Identity(configure=[Int])
drop = Drop()

inject >> f >> g >> probe >> drop

class test(Composite):
    def spec(self):
        t1 = InternalThread("t1")
        t1.run(inject, f, g, probe, drop)

    def impl(self):
        t1 = InternalThread("t1")
        t2 = InternalThread("t2")
        t1.run(inject, f)
        t2.run(g, probe, drop)

test()

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
usleep(10000);
spec_kill_threads();

impl_run_threads();
usleep(10000);
impl_kill_threads();
'''
c.desugar_mode = "compare"
c.generate_code_and_run()