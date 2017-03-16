# Prerequisites

### Dependencies

- GCC
- Python 2

### Import

To use our compiler, simply import

```python
from dsl import *
```

The library functions described in this documentation are defined in dsl.py.

# Essentials

#### 1. State

State is like C-language struct. To create an instance of a state, first you need to create a state constructor and use the state constructor to instantiate an instance of the state.

- `create_state(name, content, init=None)` returns a state constructor. A constructor can be used to create multiple instances of the state.
- `state_constructor(init=None)` returns an instance of the state.

If you only want to create one instance of a state, you can just call:

- `create_state_instance(name, content, init=None)` returns an instance of the state.

#### Example

```python
tracker_constructor = create_state("tracker", "int total; int last;", [0,0])
tracker1 = tracker_constructor()         
# ^ use the constructor's init: total = 0, last = 0
tracker2 = tracker_constructor([10,42])  
# ^ use this init: total = 10, last = 42
```

## 2. Element

An element is an executable piece of code. To create an instance of an element, first you need to create a element constructor and use the element constructor to instantiate an instance of the element.

- `create_element(name, input_ports_list, output_ports_list, c_code, local_state=None, state_params=[])` returns an element constructor. A constructor can be used to create multiple instances of the element.
- `element_constructor(instance_name=None, state_params=[])` returns an instance of the element.

If you only want to create one instance of an element, you can just call:

- `create_element_instance(instance_name, input_ports_list, output_ports_list, c_code, local_state=None, state_params=[])` returns an instance of the element.

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

See `programs/state_local.py`

## 3. Element Connection

An output port of an element can be connected to an input port of another element. Let `a`, `b`, and `c` be elements, each of which has one input port and one output port. We can connect an output port of `a` to an input port of `b`, and connect an output port of `b` to an input port of `c` by.

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

In this case, the same element `c` is executed after either `a` or `b` is executed. One thing to be caution is that both `d` and `e` are executed after `c` is executed. This is because `c` has one output port, which is connected to both `d` and `e`. 

If we want to achieve `a -> c -> d` and `b -> c -> e`, we will need multiple instances of `c` as follows. Let `C` be a constructor of `c`.

```python
c1 = C()
c2 = C()
d(c1(a(in_a)))
e(c2(b(in_b)))
```

For more examples, see `programs/hello.py`

## 4. Resource Mapping

To execute a program, you need to assign each element a thread to run. Currently, there are two types of threads: internal thread and API thread handler.

- `internal_thread(name)` returns an internal thread. An internal thread will be created automatically by our runtime system. 
- `API_thread(name, call_types, return_types, default_return=None)` returns an API thread handler. An API thread is created by a user application. 

The user application can invoke elements inside our system by calling `name`. Our system then use the application thread to execute all elements that map to such thread.

- `thread.run(e0, e1, ...)` assigns elements `e0, e1, ...` to run on `thread`. 
- `thread.run_start(e0, e1, ...)` assigns elements `e0, e1, ...` to run on `thread`, and marks `e0` as the starting element to run in each round. 
- `thread.run_order(e0, e1, ...)` assigns elements `e0, e1, ...` to run on `thread`, and impose that in each round `e0` runs before `e1`, `e1` runs before `e2`, and so on. 
- `thread.start(e)` marks `e` as the starting element to run in each round.

### 4.1 Order of Execution

What is the order of execution within a thread?

In each round, a thread starts invoke the starting element. Then, the rest of the elements assigned to the thread are executed in a topological order according to the dataflow and the order specified by `run_order`. If users erroneously assign  a starting element (e.g., the starting element requires an input from another element that is also assigned to the same thread), the compiler will throw an error. If an element assigned to a thread is unreachable (no data dependency or dependency imposed by `run_order`) from the starting element of the thread, the compiler will also throw an error. To fix this problem, introduce a partial order from the starting element to the problematic element using `run_order` (see Example 2).

For an internal thread, it will repeatedly invoke the starting element when each round is complete. For an API thread, it invokes the starting element whenever the user application calls the API.

#### Example 1

```python
hello1 = create_element_instance("Hello1", [], [], r'''printf("hello 1\n");''')
hello2 = create_element_instance("hello2", [], [], r'''printf("hello 2\n");''')

t1 = internal_thread("t1")
t2 = internal_thread("t2")
t1.run_start(hello1)
t2.run_start(hello2)
```

This program launches two threads that repeatedly print "hello 1"/"hello 2".

#### Example 2

If we want `hello1`, `hello2`, and `hello3` to run on the same thread in round-robin fashion: `hello1`, `hello2`, `hello3`, `hello1`, `hello2`, `hello3`, ... We first set `hello1` as the starting element, and introduce an order from `hello1` to `hello2`, and from `hello2` to `hello3`.

```python
t1 = internal_thread("t1")
t1.run_start(hello1, hello2, hello3)
t1.run_order(hello1, hello2, hello3)
```

If we exclude the last line, the compiler will throw an error because there is no data dependency or dependency imposed by `run_order` from the starting element `hello1` to `hello2` and `hello3`, so the compiler cannot figure out how to schedule elements to run on the thread.

### 4.2 API Thread Handler

API thread is slightly more complicated than an internal thread. It requires a user to provide the signature of the API function, and the compiler checks if it matches the inputs taken by the starting element and the outputs of the returning elements. The starting element is defined by the user; it is the first element given to `thread.run_start`. 

- The inputs to the API function are the input ports to the starting element that **have not been connected**. 
- A returning element is (i) an element that does not send any value to another element on the same thread, (ii) has only one output port, and (iii) its output port is not connected to anything. 
- An API thread handler must have zero or one returning element. If it has zero returning element, then the return type of the API is `None` (void), otherwise the return type matches the type of the output port of the returning element. Currently, our compiler only supports a returning element whose output port contains only one value.

##### Example 1

Assume we want to create an API function that increment the input by 2, and we want to do this by composing elements that increment its input by 1.

```python
Inc = create_element("Inc", [Port("in", ["int"])], [Port("out", ["int"])], 
  "int x = in() + 1; output { out(x); }")
inc1 = Inc()
inc2 = Inc()

inc2(inc1(None))

t = API_thread("add2", ["int"], "int")
t.run_start(inc1, inc2)
```

Since we want to pass the argument from the API function as an input to `inc1`, we should not connect the input port of `inc1` to anything; hence, `inc1(None)`. Similarly, we want to pass the output from `inc2` as the return value of the API function, so we should not connect the output port of `inc2` to anything.

#### Alternative Syntax

It is somewhat cumbersome to define an API function like in the last example in terms of keeping track of the input ports to the starting elements that have not been connected, and the output port of the returning element. Therefore, we introduce a different way to define an API function using a decorator `@API(name, default_return=None)`. When you use the decorator to decorate a function, all the elements declared or used within the function will be mapped to this API thread. The arguments to the API are feed as inputs to the starting element, and the return value of the API is an output of an element that is returned from the function.

##### Example 2

Below is the same program as in Example 1 but using the decorator.

```python
@API("add2")
def add2(x):
    inc1 = Inc()
    inc2 = Inc()
    return inc2(inc1(x))
```

`inc1` and `inc2` are used inside a function decorated by the API decorator, so they mapped to `add2` API thread. The argument to this API function is simply what `inc1` takes as an input, and the return value of the API function is the output of `inc2`.

#### Default Return

If an API's return type is not void, and the API may not produce a return value because some elements in the API may not fire its output ports, users have to provide a default return value to be used as the return value when the returning element of the API does not produce the return value. The default return value can be provided when creating an explicit API thread handler: `API_thread(name, call_types, return_types, default_return=None)` or decorating an API function: `@API(name, default_return=None)`

### 4.3 Blocking Buffer

What happens if an element `e1` sends its output to `e2` but they run on different threads? Consider the program below:

```python
inc1 = Inc()
inc2 = Inc()
inc2(inc1(None))

t1 = API_thread("add2_first_half", ["int"], None)
t2 = API_thread("add2_second_half", [], "int")
t1.run_start(inc1)
t2.run_start(inc2)
```

which is equivalent to:

```python
@API_implicit_outputs("add2_first_half")
def add2_first_func(x):
    return inc1(x)
    
@API_implicit_inputs("add2_second_half")
def add2_second_func(x):
    return inc2(x)
    
add2_second_func(add2_first_func(None))
```

Ignore the signatures of the two APIs for now. When this happens, the compiler will automatically create a buffer to store one entry of the output of `inc1`, and insert buffer writing and reading elements between `inc1` and `inc2`. The buffer write and read elements are blocking. If the buffer is occupied, the writing element will run in a loop until the buffer is empty and then write to the buffer. If the buffer is empty, the reading element will run in a loop until the buffer is not empty and then read from the buffer. The buffer write element becomes a part of `t1`, and the buffer read element becomes a part of `t2`. Therefore, `add2_first_half` takes one input, but return void. `add2_second_half` takes no argument, but return an integer. Essentially, if we connect an API function to an element or another API function, its signature will no longer match with the decorated function. More specifically. `add2_first_func` returns whatever `inc1` returns, but because we connect `add2_first_func` to `add2_second_func`, the API `add2_second_half` returns void. To remind the users about the mismatch, the compiler forces the users to decorate the API function with:

- `@API_implicit_inputs(name, default_return=None)`: The API function does not take any argument.
- `@API_implicit_outputs(name)`: The API function returns void.
- `@API_implicit_inputs_outputs(name)`: The API function does not take any argument and returns void.

The program above is essentially equivalent to the program below:

```python
inc1 = Inc()
inc2 = Inc()
buffer = buffer_constructor()  # buffer state
write = buffer_write_constructor([buffer])  # buffer write element
read = buffer_read_constructor([buffer])    # buffer read element

write(inc1(None))
inc2(read())

t1 = API_thread("add2_first_half", ["int"], None)
t2 = API_thread("add2_second_half", [], "int")
t1.run_start(inc1, write)
t2.run_start(read, inc2)
```

which is equivalent to:

```python
@API("add2_first_half")
def add2_first_func(x):
    write(inc1(x))
    
@API("add2_second_half")
def add2_second_func():
    return inc2(read())
```

### 4.4 Alternative Syntax for Internal Thread

Similar to `@API`, we also introduce a similar alternative syntax for mapping elements to an internal thread using a decorator `@internal_trigger(name)`. `@internal_trigger` is basically the same as `@API_implicit_inputs_outputs` in terms of how it maps elements to a thread and that its inputs come from another thread, and its outputs are sent to another thread. However, `@internal_trigger` creates an internal thread instead of an API thread handler.

For an example, see `programs/API_and_trigger.py`

### 4.5 Spawn Thread

Another kind of thread we might need is a spawn thread, which may become handy for the following scenario:

```
x1, x2 = fork(input)
y1 = proc1(x1)
y2 = proc2(x2)
output = join(y1, y2)
```

where `fork`, `proc1`, `proc2`, and `join` are elements. If we want to run `proc1` and `proc2` in parallel, we have to map them to different threads. Say we map `fork`, `proc1` and `join` to thread `t1`, and `proc2` to thread `t2`. `t2` can be an internal thread, which will run in a loop checking if an input to `proc2` is available or not. If the input is available, it runs `proc2`. Notice that `t2` is always running this loop. If `t1` is an API thread that is rarely executed, then we waste our resource on `t2` running a spinning loop. Ideally we want to spawn `t2` from `t1` every time `fork` is executed. This is something we can do if needed.

## 5. Compiling Program

### 5.1 Compile and Run

To run the program, add the following statements:

```python
c = Compiler()
c.testing = "YOUR TEST CODE"
c.generate_code_and_run()
```

Your test code can call any defined API. For example, here is the complete program that call `add2` API function:

```python
from dsl import *

Inc = create_element("Inc", [Port("in", ["int"])], [Port("out", ["int"])],
  "int x = in() + 1; output { out(x); }")
inc1 = Inc()
inc2 = Inc()

inc2(inc1(None))

t = API_thread("add2", ["int"], "int")
t.run_start(inc1, inc2)

c = Compiler()
c.testing = r'''printf("%d\n", add2(10));'''
c.generate_code_and_run()
```

When running this program, it should print out 12. The compiler generates C program `tmp.c`, which can be inspected.

We can provide a list of expected outputs from the program as an argument to `generate_code_and_run(expect)`. For example:

```
c.generate_code_and_run([12])
```

The compiler captures the stdout of the program and checks against the provided list. The list can contains numbers and strings. The stdout of the program is splitted by whitespace and newline.

If you want to the compiler to only generate the C program without running the program, you can call:

```python
c.generate_code_with_test()
```

#### Dependencies

If the C implemenations of elements require external C header files, you can set the `include` field of the compiler object to source code to include appropriate header files. For example:

```python
c.include = "#include "protocol_binary.h"
```

If the C implemenations of elements require external object files, you can set the `depend` field of the compiler object to a list of all object files (without '.o'). For example, you want to compile the program with object files jenkins_hash.o and hashtable.o:

```python
c.depend = ['jenkins_hash', 'hashtable']
```

### 5.2 Compile as Header File

Instead of generating `tmp.c`, the compiler can generate a header file instead. To generate the program as a header file, run:

```python
c.generate_code_as_header("header_file_name.h")
```

You can still provide the `include` field of the compiler object to be included in the header file.

When compiling as a header file, the application must call the following function to properly initialize and clean up the runtime system:

- `init()` initializes states for inject elements (see [Inject Element Section](#inject_element)).
- `run_threads()` creates and runs internal threads.
- `kill_threads()` kill internal threads.
- `finalize_and_check()` compares content of probe elements (see [Probe Element Section](#probe_element)).

For an example, see at the end of `memcahced_api/main.py` on how to create a header file, and see `memcahced_api/test_impl.c` on how to initialize and clean up the runtime system, and use the API functions generated by the compiler. Note that this example program uses more advanced contructs, which are explained in later sections.

## 6. Composite Element

A composite element is a collection of smaller elements. Unlike a primitive element, the entire composite element may not be executed all at once. For example, a composite element is composed of two different independent elements `a` and `b`; the input to `a` does not come from `b`, and vice versa. In such case, when the input to `a` is ready, `a` is executed; when the input to `b` is ready, `b` is executed; they don't depend on each other. However, normally elements that compose a composite element usally related to each other in some way. For example, a composite element `queue` may be composed from `enqueue` and `dequeue` elements, which share a state storing queue content.

To create an instance of a composite element, first you need to create a composite element constructor and use the element constructor to instantiate an instance of the composite element. 

- `create_composite(name, composite_function)` returns a composite constructor. A constructor can be used to create multiple instances of the composite.
- `composite_constructor(instance_name=None)` returns an instance of the composite.

### Example

A queue composite element can be created from an enqueue and dequeue element that shares a queue storage state as follows:

```python
# First create a function that defines the composite element. 
# The arguments to the function are input ports of the composite element.
# The return values of the function are output ports.
def queue_func(x):
    storage = storage_constructor()  # Create a storage state instance.
    # Create an enqueue element.
    enqueue = enqueue_constructor("enqueue", [storage])  
    # Create a dequeue element.
    dequeue = dequeue_constructor("dequeue", [storage])  
    
    # Wire connections between the input/output ports of the composite element and the internal elements,
    # and among the internal elements themselves.
    enqueue(x)  # enqueue doesn't have an output port because it writes data to the storage.
    y = dequeue()  # dequeue doesn't have an input port because it reads data from the storage.
    return y

queue_constructor =  create_composite("queue_constructor", queue_func)
queue = queue_constructor("queue")
# OR
# queue = create_composite_instance("queue", queue_func)

# Then you can use queue like a typical element.
q_in = a()
q_out = queue(q_in)
b(q_out)
```

### 6.1 Mapping Composite to One Thread

If we want to map all elements inside a composite (e.g. `compo`) to one thread (e.g. `t1`), we can simply run `t1.run(compo)`.

### 6.2 Mapping Composite to Multiple Threads

In many cases, we may want different elements inside a composite to run on different threads. Consider the `queue` composite. We probably want to run `a` and `enqueue` on thread `t1`, and `dequeue` and `b` on thread `t2`. In this case, we can make `queue_func` take threads as arguments as follows:

```python
def queue_func(x, t1, t2):
    ...
    enqueue(x)
    y = dequeue()
    t1.run(enqueue)
    t2.run_start(dequeue)  # dequeue is the starting element on t2
    return y
    
queue = create_composite_instance("queue", queue_func)
    
q_in = a()
q_out = queue(q_in, t1, t2)
b(q_out)
t1.run_start(a)
t2.run(b)
```

If we want to seperate dataflow connection from thread assignment, we can also write:

```python
# Dataflow connection
q_in = a()
q_out = queue(q_in)  # do not pass anything for thread arguments here
b(q_out)

# Thread assignment
t1.run_start(a)
t2.run(b)
queue(None, t1, t2)  # pass None for data connection
```

### 6.3 Alternative Syntax

- Use `create_composite_instance` to create a composite. See `programs/composite_at1.py` 
- Use `@composite_instance_at(name, t)` decorator to create a composite and map all elements inside the composite to thread `t`. See `programs/composite_at2.py` 
- Use `@composite_instance(name)` decorator to create a composite. See `programs/composite_at3.py`

## 7. Testing Facilities

This section describes elements and features that may be handy for testing your programs.

### 7.1 Spec/Impl

Our programming model allows users to refine their implementation by letting them implement two versions of the program side-by-side: *spec* and *impl* version. [Inject elements](#inject_element) and [probes elements](#inject_element) can be used to test the equivalence between the two implementations.

We can think of spec and impl are composite elements that should be equivalent to each other. To create an instance of spec/impl composite element, you can call:

- `create_spec_impl(name, spec_func, impl_func)` returns an instance of a spec/impl composite.

#### Example

```python
# A function defines the spec composite element. 
def spec(x):
    return inc2(x)

# A function defines the impl composite element. 
def impl(x):
    return inc1_e2(inc1_e1(x))

add2 = create_spec_impl("add2", spec, impl)
output = add2(input)
```

<a name="inject_element"></a>

### 7.2 Inject Element

An inject element is an element that takes no argument and use `gen_func` to produce a stream of values of type `type`. The length of the stream is `size`.

- `elements_library.create_inject(name, type, size, gen_func)` returns an inject element constructor. 
- `elements_library.create_inject_instance(name, type, size, gen_func)` returns an inject element.

Users must provide the implementation of `<type> gen_func(int index)` where `index` is the position of the value in the stream starting from 0.

#### Example

Let `gen_func` be:

```c
int gen_func(int i) { return i; }
```

If we create two inject elements from `create_inject_instance`:

```python
inject1 = create_inject_instance("inject1", "int", 10, "gen_func")
inject2 = create_inject_instance("inject2", "int", 10, "gen_func")
```

If `inject1` and `inject2` are fired in the order `inject1, inject2, inject1, inject2`, they will output values `0, 0, 1, 1`.

If we create two inject elements from the same constructor:

```python
inject_constructor = create_inject("Inject", "int", 40, "gen_func")
inject1 = inject_constructor("inject1")
inject2 = inject_constructor("inject2")
```

If `inject1` and `inject2` are fired in the order `inject1, inject2, inject1, inject2`, they will output values `0, 1, 2, 3`. Essentially, `inject1` and `inject2` share the same stream produced from `gen_func`.

#### Injecting Thread

If an inject element is not assigned to any thread, an inject element will run on its own internal thread. A thread that executes an inject element sleeps for 10 microseconds before starting a new round of execution. In contrast, a normal internal thread does not have any pause before starting a new round. We introduce a small pause for the injecting thread to allow the rest of computation to catch up the generated stream of values.

For an example, see `programs/join_inject.py`

<a name="probe_element"></a>

### 7.3 Probe Element

An probe element is an element that forwards an input value of type `type` without any modification and also record all the values that are passed through up to `size` number of values.

- `elements_library.create_probe(name, type, size, cmp_func)` returns a probe element constructor. 
- `elements_library.create_probe_instance(name, type, size, cmp_func)` returns a probe element.

Users must provide the implementation of `void cmp_func(int spec_n, <type> *spec_data, int impl_n, <type> *impl_data)`. The function should exit with non-zero return value if `spec_data` and `impl_data` are not equivalent. We let users implement this function because the notion of equivalence varies depending on circumstances. Sometimes, `spec_data` and `impl_data` are equivalent if they are exactly the same. The other times, `spec_data` and `impl_data` are equivalent if they contains the same values regardless of the order.

Similar to an inject element, if two probe elements are created from the same instructor, they will append the values they observe to the same storage state.

For examples of how to use inject and probe elements for testing the equivalence of spec and impl, see:

- `programs/probe_spec_impl.py`
- `programs/probe_multi.py`

## 8. Provided Elements

### 8.1 Fork

```python
elements_library.create_fork(name, n, type)
```

returns an a fork element constructor. The fork element receive a value of type `type` and fire all of its `n` output ports, passing the input value to all output ports.

Normally, we don't need a fork element because we can connect an output of an element to multiple elements. However, the fork element may become handy if we would like to fork the input from an API function.

See `programs/hello.py`

### 8.2 Drop

```python
elements_library.create_drop(name, type)
```

returns a drop element constructor. The drop element has no output port, thus dropping the input of type `type` it receives.

See `programs/probe_spec_impl.py`

### 8.2 Circular Queue

```python
queue.create_circular_queue_instances(name, type, size, blocking=False)
```

returns (`enqueue`, and `dequeue`) elements that share the same queue storage state. `type` is the type of entry in the queue. `size` is the capacity of the queue storage state. `blocking` indicates whether `enqueue` and `dequeue` are blocking when queue is full and empty, respectively.

For example, see:

- `programs/circular_queue.py`
- `programs/syscall.py`

### 8.3 Steering Circular Queue

```python
queue.create_circular_queue_one2many_instances(name, type, size, n_cores)
```

returns (`enqueue`, and `dequeues`) elements that share the same queue storage state. `dequeues` is a list of `n_cores` dequeue elements. `type` is the type of entry in the queue. `size` is the capacity of the queue storage state. This function creates a non-blocking steering queue. If the queue is full, the entry to be enqueued is dropped. If the queue is empty, dequeue returns NULL. 

`enqueue` has two input ports: the first port for receiving an entry, and the second port for receiving which core to steer the entry to (which dequeue will get the entry).

```python
queue.create_circular_queue_many2one_instances(name, type, size, n_cores)
```

returns (`enqueues`, and `dequeue`) elements that share the same queue storage state. `enqueues` is a list of `n_cores` enqueue elements. `type` is the type of entry in the queue. `size` is the capacity of the queue storage state. This function creates a non-blocking steering queue. If the queue is full, the entry to be enqueued is dropped. If the queue is empty, dequeue returns NULL. 

`dequeue` retrieve entries from `n_cores` enqueue elements in a round-robin fashion. It returns NULL if all `n_cores` queues are empty.

**Currently, we do not yet support the queue with variable-size entries.**

For an example program that uses `create_circular_queue_one2many_instances` and `create_circular_queue_many2one_instances`, see `programs/circular_queue_multicore.py`

## 9. Field Extraction

**This feature is currently not working with resource mapping. Do not try to use this at the moment.**

Given a struct, we can extract a field of a struct by creating an element to extract a field. However, for productivity, we allow users to extract field inside without creating an element.

- extract field with thread: programs/extract_field_spec_impl.py
- examples