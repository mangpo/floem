from compiler import *
from standard_elements import *
from desugaring import desugar

p = Program(
    Forward, Drop, Forward,
    Element("Choice",
            [Port("in", ["int"])],
            [Port("out1", ["int"]), Port("out2", ["int"])],
            r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }'''
            ),
    Inject("int", "inject", 10, "gen_func"),
    Probe("int", "probe[2]", 10, "cmp_func"),
    Spec(
        ElementInstance("Forward", "f1"),
        ElementInstance("Forward", "f2"),
        Connect("inject", "f1"),
        Connect("f1", "f2"),
        Connect("f2", "probe[0]"),
    ),
    Impl(
        ElementInstance("Choice", "c"),
        ElementInstance("Forward", "f1"),
        ElementInstance("Forward", "f2"),
        Connect("inject", "c"),
        Connect("c", "f1", "out1"),
        Connect("c", "f2", "out2"),
        Connect("f1", "probe[0]"),
        Connect("f2", "probe[1]")
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
  _impl_inject();
  _impl_inject();
'''
generate_code_with_test(g, testing, include)
generate_code_and_run(g, testing, expect=None, include=include)
