from compiler import *
from standard_elements import *

p = Program(
    PopulateState("inject", "inject_s", "InjectState", "int", 10, "gen_func"),
    CompareState("probe", "probe_s", "InjectState", "int", 10, "cmp_func"),
    Composite("Spec",
              [],
              [],
              [],
              [],
              Program(
                  Forward, Drop,
                  InjectProbeState("InjectState", "int", 10),
                  InjectElement("Inject", "int", "InjectState", 10),
                  ProbeElement("Probe", "int", "InjectState", 10),
                  ElementInstance("Forward", "f1"),
                  ElementInstance("Forward", "f2"),
                  ElementInstance("Drop", "drop"),

                  StateInstance("InjectState", "inject_s"),
                  StateInstance("InjectState", "probe_s"),

                  ElementInstance("Inject", "inject", ["inject_s"]),
                  ElementInstance("Probe", "probe", ["probe_s"]),

                  # Connect("f1", "inject"),
                  Connect("inject", "f2"),
                  Connect("f2", "probe"),
                  Connect("probe", "drop"),
              )),
    Composite("Impl",
              [],
              [],
              [],
              [],
              Program(
                  Forward,
                  InjectProbeState("InjectState", "int", 10),
                  InjectElement("Inject", "int", "InjectState", 10),
                  ProbeElement("Probe", "int", "InjectState", 10),
                  ElementInstance("Forward", "f1"),
                  ElementInstance("Forward", "f2"),

                  StateInstance("InjectState", "inject_s"),
                  StateInstance("InjectState", "probe_s"),

                  ElementInstance("Inject", "inject", ["inject_s"]),
                  ElementInstance("Probe", "probe", ["probe_s"]),

                  #Connect("f1", "inject"),
                  Connect("inject", "f2"),
                  Connect("f2", "probe"),

                  APIFunction("read", "f2", None, "probe", "out", "int")
              )),
    CompositeInstance("Spec", "spec"),
    CompositeInstance("Impl", "impl")
)

g = generate_graph(p)
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
_spec_inject_s.data[0] = _impl_inject_s.data[0] = 42;
_spec_inject_s.data[1] = _impl_inject_s.data[1] = 123;

_spec_inject();
_spec_inject();

_impl_inject();
read();
_impl_inject();
read();

printf("%d\n", _spec_inject_s.p);
for (int i=0; i < _spec_inject_s.p; i++)
    printf("%d\n", _spec_inject_s.data[i]);

printf("%d\n", _impl_inject_s.p);
for (int i=0; i < _impl_inject_s.p; i++)
    printf("%d\n", _impl_inject_s.data[i]);
'''
generate_code_and_run(g, testing, [2, 42, 123, 2, 42, 123], include)