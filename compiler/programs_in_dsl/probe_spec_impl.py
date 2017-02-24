from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Inject = create_inject("inject", "int", 10, "gen_func")
Probe = create_probe("probe", "int", 10, "cmp_func")
Drop = create_drop("Drop", "int")

inject = Inject()
probe = Probe()
f1 = Forward("f1")
f2 = Forward("f2")
drop = Drop()

drop(probe(f2(f1(inject()))))

def spec():
    return

def impl():
    t1 = internal_thread("t1")
    t2 = internal_thread("t2")
    t1.run_start(inject, f1)
    t2.run_start(f2, probe, drop)

compo = create_spec_impl("compo", spec, impl)

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
run_threads();
usleep(100000);
kill_threads();
'''
c.desugar_mode = "compare"
c.triggers = True
c.generate_code_and_run()