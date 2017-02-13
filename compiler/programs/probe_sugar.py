from compiler import *
from standard_elements import *
from desugaring import desugar

p = Program(
    Forward, Drop, Forward,
    Inject("int", "inject", 10, "gen_func"),
    Probe("int", "probe", 10, "cmp_func"),
    ElementInstance("Forward", "f1"),
    ElementInstance("Forward", "f2"),
    Spec(
        Connect("inject", "f1"),
        Connect("f1", "f2"),
        Connect("f2", "probe"),
    ),
    Impl(
        Connect("inject", "f1"),
        Connect("f1", "f2"),
        Connect("f2", "probe"),
        InternalTrigger("f2")
    )
)

dp = desugar(p, "compare")
g = generate_graph(dp)

include = r'''
int gen_func(int i) { return i; }
int cmp_func(int spec_n, int *spec_data, int impl_n, int *impl_data) {
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
}
'''
testing = r'''
  _spec_inject();
  _spec_inject();
  _spec_inject();

  _impl_inject();
  _buffer__impl_f2_read();
  _impl_inject();
  _buffer__impl_f2_read();
  _impl_inject();
  _buffer__impl_f2_read();
'''
generate_code_with_test(g, testing, include)
generate_code_and_run(g, testing, expect=None, include=include)
