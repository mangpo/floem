Our prototyping DSL is a Python Library. The library provides mechanisms to connect elements, mapping elements to hardware resources, and create API functions for user applications. However, an element itself is implemented in C. The compiler then generates C program that can be executed.

# Prerequisites

### Dependencies

- GCC
- Python 2
- DPDK

### Repository

```
git clone git@gitlab.cs.washington.edu:mangpo/flexnic-language-mockup.git
cd compiler
```

### Import

To use our compiler, simply import

```python
from dsl2 import *
```

Queue library is defined in queue2.py

# Essentials

## 1. State

State is like C-language struct. To create an instance of a state, first you need to create a state class and use the state class to instantiate an instance of the state.

#### Example

```python
class Tracker(State):
  total = Field(Int)
  last = Field(Int)
  
  def init(self, total=0, last=0):
    self.total = total
    self.last = last
    
tracker1 = Tracker()
# ^ use the constructor's init: total = 0, last = 0
tracker2 = Tracker(init=[10,42])  
# ^ use this init: total = 10, last = 42
```

## 2. Element

An element is an executable piece of code. To create an instance of an element, first you need to create a element class and use the element class to instantiate an instance of the element.

#### Example

```python
class Observer(Element):
  tracker = Persistent(Tracker)  # State of this element that is persist across all packets
  def states(self, tracker): self.tracker = tracker
  
  def configure(self):
    self.inp = Input(Int)   # Input port
    self.out = Output(Int)  # Output port
    
  def impl(self):
    self.run_c(r'''
      int id = inp();     // Retrieve a value from inp input port.
      tracker->total++;   // State is referenced as a pointer to a struct.
      tracker->last = id; 
      output { out(id); }
    ''')
    
o1 = Observer(states=[tracker1])  # observer element 1
o2 = Observer(states=[tracker1])  # observer element 2
```

Notice that `o1` and `o2` share the same tracker state, so they both contribute to `tracker1->total`. Also notice that there can be a race condition here because of the shared state.

### 2.1 Element Port

Input and output ports are defined in `configure` method.
```
self.<port_name> = [Input | Output](arg_type0, arg_type1, ...)
```

### 2.2 Element's Implementation (C Code)

#### Inputs

An element retrieves its input(s) by calling its input ports, e.g. `int id = inp();`. If an input port contains multiple values, an element can retrieves multiple values using a tuple, e.g. `(int id1, int id2) = in();`

#### Outputs

An element send outputs by calling its output ports `e.g. output{ out(id); }`. The output ports can only be called within the output block `output { ... }` or `output switch { ... }`. An element must fire: (i) all its output ports, (ii) one of its output ports, or (iii) zero or one of its output ports.

With an exception of a *looping* element, which can fire its only one output port many times outside the output block.

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

##### (iv) Fire an output port many times (looping element)

```c
for(int i=0; i<10; i++) out(i);  // An output port can be called anywhere in the code.
output multiple;  // Annotate that this element fires an output port multiple times.
```

## 3. Element Connection

An output port of an element can be connected to an input port of another element. Let `a`, `b`, and `c` be elements, each of which has one input port and one output port. We can connect an output port of `a` to an input port of `b`, and connect an output port of `b` to an input port of `c` by.

```python
a >> b >> c
```

#### Multiple Input Ports
If an element has multiple input ports, users must specify which port to connect explicitly.

```python
a >> c.in0
b >> c.in1
```

#### Multiple Output Ports
If an element has multiple output ports, users must specify which port to connect explicitly.

```python
a.out0 >> b
a.out1 >> c
```

### Example 1

An output port of an element can be connected to multiple elements.

```python
a >> b
a >> c
```

### Example 2

If `a` fires only one of its output port, either `b` or `c` will be executed (not both).

```python
a.out0 >> b
a.out1 >> c
```

### Example 3

An input port of an element can be connected from multiple elements.

```python
a >> c >> d
b >> c >> e
```

In this case, the same element `c` is executed after either `a` or `b` is executed. One thing to be caution is that both `d` and `e` are executed after `c` is executed. This is because `c` has one output port, which is connected to both `d` and `e`. 

If we want to achieve sperate flows of `a -> c -> d` and `b -> c -> e`, we will need multiple instances of `c` as follows. Let `C` be a constructor of `c`.

```python
c1 = C()
c2 = C()
a >> c1 >> e
a >> c2 >> e
```

## 4. Mapping Elements to Threads

To execute a program, you need to assign each element a thread to run. Currently, there are two types of threads: internal thread and API thread handler.

- `InternalThread(name)` returns an internal thread. An internal thread will be created automatically by our runtime system. 
- `APIThread(name, call_types, return_types, default_return=None)` returns an API thread handler. An API thread is created by a user application. 

The user application can invoke elements inside our system by calling `name`. Our system then use the application thread to execute all elements that map to such thread.

- `thread.run(e0, e1, ...)` assigns elements `e0, e1, ...` to run on `thread`.  
- `thread.run_order(e0, e1, ...)` assigns elements `e0, e1, ...` to run on `thread`, and impose that in each round `e0` runs before `e1`, `e1` runs before `e2`, and so on.

### 4.1 Order of Execution

What is the order of execution within a thread?

In each round, a thread starts invoke the starting element (an element that doesn't has any data dependency or dependency imposed by `run_order` on other elements of the same thread). Then, the rest of the elements assigned to the thread are executed in a topological order according to the dataflow and the order specified by `run_order`. If an element assigned to a thread is unreachable (no data dependency or dependency imposed by `run_order`) from the starting element of the thread, the compiler will also throw an error. To fix this problem, introduce a partial order from the starting element to the problematic element using `run_order` (see Example 2).

For an internal thread, it will repeatedly invoke the starting element when each round is complete. For an API thread, it invokes the starting element whenever the user application calls the API.

#### Example 1

```python
class Hello(Element):
  def configure(self, c):  self.c = c
  def impl(self): self.run_c(r'''printf("hello %d\n");''' % self.c)

hello1 = Hello(configure=[1])
hello2 = Hello(configure=[2])

t1 = InternalThread("t1")
t2 = InternalThread("t2")
t1.run(hello1)
t2.run(hello2)
```

This program launches two threads that repeatedly print "hello 1"/"hello 2".

#### Example 2

If we want `hello1`, `hello2`, and `hello3` to run on the same thread in round-robin fashion: `hello1`, `hello2`, `hello3`, `hello1`, `hello2`, `hello3`, ... We introduce an order from `hello1` to `hello2`, and from `hello2` to `hello3` as follows.

```python
t1 = InternalThread("t1")
t1.run_order(hello1, hello2, hello3)
```

If we use `run` instead of `run_order` on the last line, the compiler will throw an error because there are multiple potential starting elements.

### 4.2 API Thread Handler

API thread is slightly more complicated than an internal thread. It requires a user to provide the signature of the API function, and the compiler checks if it matches the inputs taken by the starting element and the outputs of the returning elements.

- The inputs to the API function are the input ports to the starting element that **have not been connected**. 
- A returning element is (i) an element that does not send any value to another element on the same thread, (ii) has only one output port, and (iii) its output port is not connected to anything. 
- An API thread handler must have zero or one returning element. If it has zero returning element, then the return type of the API is `None` (void), otherwise the return type matches the type of the output port of the returning element. Currently, our compiler only supports a returning element whose output port contains only one value.

##### Example 1

Assume we want to create an API function that increment the input by 2, and we want to do this by composing elements that increment its input by 1.

```python
class Inc(Element):
  def configure(self):
    self.inp = Input(Int)
    self.out = Output(Int)
    
  def impl(self):
    self.run_c("int x = inp() + 1; output { out(x); }")
    
inc1 = Inc()
inc2 = Inc()

inc1 >> inc2

t = API_thread("add2", ["int"], "int")
t.run(inc1, inc2)
```

Since we want to pass the argument from the API function as an input to `inc1`, we don't connect the input port of `inc1` to anything. Similarly, we want to pass the output from `inc2` as the return value of the API function, so we don't connect the output port of `inc2` to anything.

#### Alternative Syntax

It is somewhat cumbersome to define an API function like in the last example in terms of keeping track of the input ports to the starting elements that have not been connected, and the output port of the returning element. Therefore, we introduce a different way to define an API function using `API` class. When you use `API` class, all the elements declared or used within the `impl` method of `API` will be mapped to this API thread. The arguments to the input ports are argument to the API. The arguments to the output ports are the return values. If there are multiple input ports, the order of arguments follow the order of ports defined in the method `args_order` (see `programs_dsl2/API_insert_start_element.py`).


##### Example 2

Below is the same program as in Example 1 but using the `API` class.

```python
class add2(API):
  def configure(self):
    self.inp = Input(Int)
    self.out = Output(Int)
    
  def impl(self):
    self.inp >> Inc() >> Inc() >> self.out
```

#### Default Return

If an API's return type is not void, and the API may not produce a return value because some elements in the API may not fire its output ports, users have to provide a default return value to be used as the return value when the returning element of the API does not produce the return value. The default return value can be provided when creating an explicit API thread handler: `APIThread(name, call_types, return_types, default_return=None)` or assigning to the field `self.default_return` of an `API` object.

### 4.3 Blocking Buffer

What happens if an element `e1` sends its output to `e2` but they run on different threads? Consider the program below:

```python
inc1 = Inc()
inc2 = Inc()
inc1 >> inc2

t1 = APIThread("add2_first_half", ["int"], None)
t2 = APIThread("add2_second_half", [], "int")
t1.run(inc1)
t2.run(inc2)
```

Ignore the signatures of the two APIs for now. When this happens, the compiler will automatically create a buffer to store one entry of the output of `inc1`, and insert buffer writing and reading elements between `inc1` and `inc2`. The buffer write and read elements are blocking. If the buffer is occupied, the writing element will run in a loop until the buffer is empty and then write to the buffer. If the buffer is empty, the reading element will run in a loop until the buffer is not empty and then read from the buffer. The buffer write element becomes a part of `t1`, and the buffer read element becomes a part of `t2`. Therefore, `add2_first_half` takes one input, but return void. `add2_second_half` takes no argument, but return an integer. Essentially, if we connect an API function to an element or another API function, its signature will no longer match with the decorated function. More specifically. `add2_first_func` returns whatever `inc1` returns, but because we connect `add2_first_func` to `add2_second_func`, the API `add2_second_half` returns void. 

The program above is essentially equivalent to the program below:

```python
inc1 = Inc()
inc2 = Inc()
buffer = Buffer()  # buffer state
write = BufferWrite(states=[buffer])  # buffer write element
read = BufferRead(states=[buffer])    # buffer read element

inc1 >> write
read >> inc2

t1 = APIThread("add2_first_half", ["int"], None)
t2 = APIThread("add2_second_half", [], "int")
t1.run(inc1, write)
t2.run(read, inc2)
```

### 4.4 Alternative Syntax for Internal Thread

Similar to `API`, we also introduce a similar alternative syntax for mapping elements to an internal thread using class `InternalLoop`. 

### 4.5 Spawn Thread

Another kind of thread we might need is a spawn thread, which may become handy for the following scenario:

```
fork.out1 >> proc1 >> join.in1
fork.out2 >> proc2 >> join.in2
```

where `fork`, `proc1`, `proc2`, and `join` are elements. If we want to run `proc1` and `proc2` in parallel, we have to map them to different threads. Say we map `fork`, `proc1` and `join` to thread `t1`, and `proc2` to thread `t2`. `t2` can be an internal thread, which will run in a loop checking if an input to `proc2` is available or not. If the input is available, it runs `proc2`. Notice that `t2` is always running this loop. If `t1` is an API thread that is rarely executed, then we waste our resource on `t2` running a spinning loop. Ideally we want to spawn `t2` from `t1` every time `fork` is executed. This is something we can do if needed.

## 5. Mapping Threads to Processes
Set `self.process` of an `API` or `InternalLoop` object to the name of the process (generated c source file) you want to map the thread to. If `self.process` is unspecified, all threads will map to `tmp` process.

## 6. Compiling Program

### 6.1 Compile and Run

To run the program, add the following statements:

```python
c = Compiler()
c.testing = "YOUR TEST CODE"
c.generate_code_and_run()
```

Your test code can call any defined API. For example, here is the complete program that call `add2` API function:

```python
from library_dsl2 import *

class add2(API):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        inc1 = Inc('inc1', configure=[Int])
        inc2 = Inc('inc2', configure=[Int])
        self.inp >> inc1 >> inc2 >> self.out

add2('add2')

c = Compiler()
c.testing = "out(add2(11));"
c.generate_code_and_run()
```

When running this program, it should print out 12. The compiler generates C program `tmp.c`, which can be inspected.

We can provide a list of expected outputs from the program as an argument to `generate_code_and_run(expect)`. For example:

```
c.generate_code_and_run([12])
```

The compiler captures the stdout of the program and checks against the provided list. The list can contains numbers and strings. The stdout of the program is splitted by whitespace and newline.


#### Dependencies

If the C implemenations of elements require external C header files, you can set the `include` field of the compiler object to source code to include appropriate header files. For example:

```python
c.include = "#include "protocol_binary.h"
```

If the C implemenations of elements require external object files, you can set the `depend` field of the compiler object to a list of all object files (without '.o'). For example, you want to compile the program `test1` with object files jenkins_hash.o and hashtable.o and compile `test2` with just jenkins_hash.o:

```python
c.depend = {'test1': ['jenkins_hash', 'hashtable'], 'test2': ['jenkins_hash']}
```

### 6.2 Compile as Header File

Instead of generating `.c`, the compiler can generate a header file instead. To generate the program as a header file, run:

```python
c.generate_code_as_header()
```

You can still provide the `include` field of the compiler object to be included in the header file.

When compiling as a header file, the application must call the following function to properly initialize and clean up the runtime system:

- `init()` initializes states and inject elements (see [Inject Element Section](#inject_element)).
- `run_threads()` creates and runs internal threads.
- `kill_threads()` kill internal threads.
- `finalize_and_check()` compares content of probe elements (see [Probe Element Section](#probe_element)).

For an example, see at the end of `storm_queue/main_socket_local2.py` on how to create a header file, and see `storm_queue/test_storm.c` on how to initialize and clean up the runtime system, and use the API functions generated by the compiler. 

## 7. Composite Element

A composite element is a collection of smaller elements. Unlike a primitive element, the entire composite element may not be executed all at once. For example, a composite element is composed of two different independent elements `a` and `b`; the input to `a` does not come from `b`, and vice versa. In such case, when the input to `a` is ready, `a` is executed; when the input to `b` is ready, `b` is executed; they don't depend on each other. However, normally elements that compose a composite element usally related to each other in some way. For example, a composite element `queue` may be composed from `enqueue` and `dequeue` elements, which share a state storing queue content.

To create an instance of a composite element, first you need to create a composite element constructor and use the element constructor to instantiate an instance of the composite element. 

### Example

A queue composite element can be created from an enqueue and dequeue element that shares a queue storage state as follows:

```python
class Queue(Composite):
  def configure(self):
    self.inp = Input(Entry)
    self.out = Oput(Entry)
    
  def impl(self):
    storage = Storage()  # Create a storage state.
    enq = Enqueue(states=[storage])
    deq = Dequeue(states=[storage])
    self.inp >> enq
    deq >> self.out
    
queue = Queue()

# Then you can use queue like a typical element.
a >> queue >> b
```

### 7.1 Mapping Composite to One Thread

If we want to map all elements inside a composite (e.g. `compo`) to one thread (e.g. `t1`), we can simply run `t1.run(compo)`.

### 7.2 Mapping Composite to Multiple Threads

TODO

## 8. Testing Facilities

This section describes elements and features that may be handy for testing your programs.

## 9. Provided Elements

### 9.1 Queue

See `queue2.py`

### 9.2 FROM_NET/TO_NET

See `net2.py`

## 10. Field Extraction

## 11. Example Application: Memcached
## 12. Example Application: Storm
See `storm_queue/main_socket_local2.py`. Using unix TCP sockets for communication.

