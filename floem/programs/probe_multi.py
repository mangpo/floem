from library import *
from compiler import Compiler

Inject = create_inject("inject", "int", 10, "gen_func")
Probe = create_probe("probe", "int", 10, "cmp_func")

class Choice(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out1 = Output(Int)
        self.out2 = Output(Int)

    def impl(self):
        self.run_c(r'''
        (int x) = inp(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }
        ''')

inject = Inject()
f1 = Identity(configure=[Int])
f2 = Identity(configure=[Int])
drop = Drop()

class test(Composite):
    def spec(self):
        probe = Probe()
        inject >> f1 >> f2 >> probe >> drop

    def impl(self):
        probe1 = Probe()
        probe2 = Probe()
        choice = Choice()
        inject >> choice
        choice.out1 >> f1 >> probe1 >> drop
        choice.out2 >> f2 >> probe2 >> drop

compo = test()
t = InternalThread("t")
t.run(compo)


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