## Prerequisites
- GCC
- Python2

# Programming Model Constructs
## 1. State
State is like C struct. To create an instance of a state, first you need to create a state constructor and use the state constructor to instantiate an instance of the state.

`dsl.create_state(name, content, init=None)` returns a state constructor. A constructor can be used to create multiple instances of the state.
`state_constructor(init=None)` returns an instance of the state.

If you only want to create one instance of a state, you can just call:

`dsl.create_state_instance(name, content, init=None)` returns an instance of the state.

#### Example
```python
tracker_constructor = create_state("tracker", "int total; int last;", [0,0])
tracker1 = tracker_constructor()         # use the constructor's init: total = 0, last = 0
tracker2 = tracker_constructor([10,42])  # use this init: total = 10, last = 42
```

## 2. Element
An element is an executable piece of code. To create an instance of a state, first you need to create a element constructor and use the element constructor to instantiate an instance of the element.

`dsl.create_element(name, input_ports_list, output_ports_list, c_code, local_state=None, state_params=[])` returns an element constructor. A constructor can be used to create multiple instances of the element.
`element_constructor(instance_name=None, state_params=[])` returns an instance of the element.

If you only want to create one instance of an element, you can just call:

`dsl.create_element_instance(instance_name, input_ports_list, output_ports_list, c_code, local_state=None, state_params=[])` returns an instance of the element.

#### Example
```python
obs_constructor = create_element("observer", 
  [Port("in", ["int"])], 
  [Port("out", ["int"])],
  "int id = in(); this.total++; this.last = id; output { out(id); }",
  None,
  [("tracker", "this")])  # state params = a list of (state, local_name)
o1 = obs_constructor(tracker1)  # observer element 1
o2 = obs_constructor(tracker1)  # observer element 2
```
Notice that `o1` and `o2` share the same tracker state, so they both contribute to `tracker1.total`. Also notice that there can be a race condition here because of the shared state.

### 2.1 Element Port
A element is defined with a list of input and output ports. A port is `graph.Port(<name>, <list of types>)`.

### 2.2 Element's Implementation (C Code)
#### Inputs
An element retrieves its input(s) by calling its input ports, e.g. `int id = in();`. If an input port contains multiple values, an element can retrieves multiple values using a tuple, e.g. `(int id1, int id2) = in();`

#### Outputs
An element send outputs by calling its output ports `e.g. output{ out(id); }`. The output ports can only be called within the output block `output { ... }` or `output switch { ... }`. An element must fire: (i) all its output ports, (ii) one of its output ports, or (iii) zero or one of its output ports.

##### (i) Fire all output ports
In this case, all ports must be called inside the output block `output { ... }`.

##### (ii) Fire one of its output ports
In this case, the output block 
```c
output switch { 
  case <cond1>: <out1>(<args1>); 
  case <cond2>: <out2>(args2>); 
  ... 
  else: <outN>(argsN); 
  }
```
must be used. For example, `output switch { case (id < 10): out1(id); else: out2(id); }`.

##### (iii) Fire zero or one of its output ports
Similar to (ii), `output switch` block is used, but without the `else` case.

### 2.3 Element's Local State
See `programs_in_dsl/state_local.py`

## 3. Element Connection

An output port of an element can be connected to an input port of another element. Let `a`, `b`, and `c` be elements, each of which has one input port and one output port. We can connect an output port of `a` to an input port of `b`, and connect an output port of `b` to an inport of `c` by.

```python
out_a = a(None)
out_b = b(out_a)
out_c = c(out_b)
# OR
out_c = c(b(a(None)))
```
Notice that we supply `None` as an argument to `a`. This is because `a` requires one input port, but we current do not want to connect it to anything. Alternatively, `a` can be called without any argument `a()`, and the effect is exactly the same. However, `None` helps remind that `a`'s input port is not connected to anything yet.

#### Multiple Input Ports
```python
out_a = a(in_a1, in_a2)
```
#### Multiple Output Ports
```python
out_a1, out_a2 = a(in_a)
```

### Example 1
An output port of an element can be connected to multiple elements.
```python
out_a = a(in_a)
out_b = b(out_a)
out_c = c(out_a)
```

### Example 2
If `a` fires only one of its output port, either `b` or `c` will be executed (not both).
```python
out_a1, out_a2 = a(in_a)
out_b = b(out_a1)
out_c = c(out_a2)
```

### Example 3
An input port of an element can be connected from multiple elements.
```python
out_a = a(in_a)
out_b = b(in_b)
out_c1 = c(out_a)
out_c2 = c(out_b)
d(out_c1)
e(out_c2)
```
In this case, the same element `c` is executed after either `a` or `b` is exectued. One thing to be caution is that both `d` and `e` are executed after `c` is executed. This is because `c` has one output port, which is connected to both `d` and `e`. 

If we want to acheive `a -> c -> d` and `b -> c -> e`, we will need multiple instances of `c` as follows. Let `C` be a constructor of `c`.
```python
c1 = C()
c2 = C()
d(c1(a(in_a)))
e(c2(b(in_b)))
```

For more examples, see
- `programs_in_dsl/hello.py`
- `programs_in_dsl/join.py`

## 4. Composite Element

## 5. Resource Mapping

### 5.1 API Thread

### 5.2 Internal Thread

- thread and composite

## 6. Testing Facilities



