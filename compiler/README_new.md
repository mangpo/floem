# Floem
Floem is a DSL, compiler, runtime for NIC-accelerated network applications. Currently, the compiler can generate code for
- a system with only a CPU with DPDK
- a system with a CPU and Cavium LiquidIO nic

The DSL is a Python Library. The library provides mechanisms to connect elements, mapping elements to hardware resources, and create function interfacess for external applications. An element itself is implemented in C. The compiler then generates C program that can be executed.

# Table of Contents
A. [Prerequisites](#Prerequisites)
B. [Language](#Language)
  1. [State](#State)
  2. [Element](#Element)
  3. [Element Connection](#Element-Connection)
  
C. [Running on Cavium](#Running-on-Cavium)
D. [Compiler's Options](#Compilers-Options)


# A. Prerequisites

### Dependencies

- GCC
- Python 2

For a CPU-only system, you require [DPDK](http://dpdk.org/) to be installed. Set variable `dpdk_dir` in `compiler/target.py` to DPDK directory's path. If you do not intent to use DPDK, leave the variable as is.

For a system with a Cavium LiquidIO NIC, you require Cavium SDK and this [repository](https://gitlab.cs.washington.edu/mangpo/LiquidIOII-UseCase), containing source and binary for LiquidIO driver and firmware with Floem runtime.

### Setup

Add the `compiler` directory into your evironment path.
```
export PYTHONPATH=/path/to/repo/compiler
```

### Import

To use Floem, simply import `floem` in your python program.

```python
from floem import *
```

# B. Language

## 1. Element

An element is an executable piece of code. To create an instance of an element, first you need to create a element class and use the element class to instantiate an instance of the element.

#### Example

```python
class Inc(Element):
  def configure(self):
    self.inp = Input(Int)   # Input port
    self.out = Output(Int)  # Output port
    
  def impl(self):
    self.run_c(r'''
      int x = inp();        // Retrieve a value from input port inp.
      output { out(x+1); }  // Sent a value to output port out.
    ''')
    
inc = Inc()  # create an element
```


### 1.1 Element Port

Input and output ports are defined in `configure` method.
```
self.<port_name> = [Input | Output](arg_type0, arg_type1, ...)
```

##### Data Type
Provided data types are 
- `Void` (void), `Bool` (bool), `Int` (int), `SizeT` (size_t), `Float` (float), and `Double` (double)
- `Uint(<bits>)` represents uint<bits>_t
- `Sint(<bits>)` represents int<bits>_t
- `Pointer(<type>)` represents pointer of <type>
- `Array(<type>, <size>)` represents array of <type> with size <size>

Users can create a composite data type (struct) using [State](#State). To refer to a struct in a C header file defined outside Floem, users can simply use string. For example, `self.inp = Input("struct tuple *")` is an input port that accepts a pointer to `struct tuple` defined outside Floem.

**See xxx as an example when data type is a state defined using Floem.**
**See xxx as an exmpale when data type is a struct defined outside Floem.** 

### 1.2 Element's Implementation (C Code)

#### Inputs

An element retrieves its input(s) by calling its input ports, e.g. `int id = inp();`. If an input port contains multiple values, an element can retrieves multiple values using a tuple, e.g. `(int id1, int id2) = in();`

#### Outputs

An element sends outputs by calling its output ports `e.g. output{ out(id); }`. The output ports can only be called within the output block `output { ... }` or `output switch { ... }`. An element must fire: (i) all its output ports, (ii) one of its output ports, or (iii) zero or one of its output ports. With an exception of a *looping* element, which can fire its only one output port many times outside the output block.

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

## 2. Element Connection

An output port of an element can be connected to an input port of another element. Let `a`, `b`, and `c` be elements, each of which has one input port and one output port. We can connect an output port of `a` to an input port of `b`, and connect an output port of `b` to an input port of `c` by.

```python
a >> b >> c
```

### Multiple Input Ports
If an element has multiple input ports, users must specify which port to connect explicitly.

```python
a >> c.in0
b >> c.in1
```

### Multiple Output Ports
If an element has multiple output ports, users must specify which port to connect explicitly.

```python
a.out0 >> b
a.out1 >> c
```


##### Example 1

An output port of an element can be connected to multiple elements.

```python
a >> b
a >> c
```

##### Example 2

If `a` fires only one of its output port, either `b` or `c` will be executed (not both).

```python
a.out0 >> b
a.out1 >> c
```

##### Example 3

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

### Type Check
An output port `out` of an element `a` can be connected to an input port `inp` of an element `b` if their data types match. Otherwise, the compiler will throw an exception.

For one special case, an output port `out` of an element `a` can also be connected to an input port `inp` of an element `b` even when their types do not match, with the condition that port `inp` must has zero argument. In this case, the element `a` simply drops arguments that supposed to be sent to the element `b`. We introduce this feature as we find it to be quite convenient.

## 3. Pipeline

To execute a program, you need to assign an element to a *pipeline* to run. A pipeline is a set of connected elements that starts from a *source element* and ends at leaf elements (elements with no output ports) or queues. Packet handoff along a pipeline is initiated by the source element pushing a packet to subsequent elements. 

### 3.1 Normal Pipeline
By default, a pipeline is executed by one dedicated thread on a device, so elements within a pipeline run sequentially with respect to packet-flow dependencies. To create a pipeline and make the pipeline runs elements `a >> b` sequentially, write

```python
class P(Pipeline):
  def impl(self):
     a >> b
     
P('pipeline_name')
```

A thread starts invoke the source node (an element that doesn't has any data dependency). Then, the rest of the elements are executed in a topological order according to the dataflow. A thread repeats the execution of the pipeline forever. If an element assigned to a pieline is unreachable (no data dependency) from the source element, the compiler will throw an error. In the current implementation, if there is no dependency between elements `x` and `y` according to the dataflow, `x` is executed before `y` if `x` appears before `y` in the program.

##### Compile and Run
To compile all the defined pipelines into an executable file, add the following code in your program:
```python
c = Compiler()
c.testing = "while(1) pause();"
c.generate_code_and_run()
```

`c.testing` is the body of the main function. In this case, we want the main function to run forever.

Under the hood, 
1. Floem compiler compiles all pipelines to `tmp.c`. 
2. GCC compiles `tmp.c` to executable `tmp`. 
3. `tmp` is then executed for a few second by the script. 

All the generated files remain after the compilation process is done. Therefore, `tmp` can be executed later using command line.
**See xxx for an exmaple.**

##### Dependencies

If the C implemenations of elements require external C header files, we can set the `include` field of the compiler object to include appropriate header files. For example:

```python
c.include = "#include "protocol_binary.h"
```

If the C implemenations of elements require external object files, we can set the `depend` field of the compiler object to a list of all object files (without '.o'). For example, we want to compile the program with object files jenkins_hash.o and hashtable.o:

```python
c.depend = ['jenkins_hash', 'hashtable']
```
The compiler will first compile each C program in `c.depend` to an object file, and then compile `tmp.c` with all the object files.
**See xxx for an exmaple.**

##### Testing
We can provide a list of expected outputs from the program as an argument to `generate_code_and_run(expect)`. For example:

```
c.generate_code_and_run([12])
```

The compiler captures the stdout of the program and checks against the provided list. The list can contains numbers and strings. The stdout of the program is splitted by whitespace and newline.


### 3.2 Callable Pipeline

To enable programmers to offload their existing applications to run on a NIC without having to port their entire applications into Floem, we introduce a *callable pipeline*, which is a pipeline that is exposed as a function that can be called from any C program. This way, programmers have to port only the parts they want to offload to a NIC into Floem.

Programmers can create a callable pipeline similar to a normal pipeline, but additionally, they must define the argument types and the return type of the function via an input and output port of the pipeline. Note that a callable pipeline can take multiple input arguments though one input port. A callable pipeline can return nothing (no output port) or return one return value via an output port.

For example, we can create a function `inc2` (a function that returns its argument added by 2) from element `Inc` (an element that increments its input by 1) as follows.

```python
class Inc(Element):
  def configure(self):
    self.inp = Input(Int)
    self.out = Output(Int)
    
  def impl(self):
    self.run_c("int x = inp() + 1; output { out(x); }")
    
class inc2(CallablePipeline):
  def configure(self):
    self.inp = Input(Int)
    self.out = Output(Int)
    
  def impl(self):
    self.inp >> Inc() >> Inc() >> self.out
    
inc2('inc2', process='simple_math')
```
The function `inc2` can be used in any C program like a normal C function. To use the function, users have to including `#include "simple_math.h"`. Notice that you can choose the name of the header to include.

##### Compile and Run 1
Similar to normal pipelines, we can compile callable pipelines using the same commands:
```python
c = Compiler()
c.testing = r'''
int x = inc2(42);
printf("%d\n", x);
'''
c.generate_code_and_run()
```
Notice, that the main body can call function `inc2`. The compiler generates executable `tmp` similar to how it is done for normal pipelines. This method for compiling and running is good for testing, but not suitable for an actual use because we want to use function `inc2` in any C program not in `tmp.c` where it is defined.

**See xxx for an exmaple.**

##### Compile and Run 2
To compile callable pipelines to be used in any external C program, we write:
```python
c = Compiler()
c.generate_code_as_header('simple_math')
c.depend = ['simple_math']
c.compile_and_run('external_program')
```
The code shows how to use Floem to compile an external C program `external_program.c` that calls function `inc2` written in Floem. Under the hood, 
1. Floem generates `simple_math.c` that contains actual implementation of `inc2` and `simple_math.h` that contains the function signature. 
2. GCC compiles all C programs listed in `c.depend` into object files (compiles `simple_math.c` to `simple_math.o`). 
3. GCC compiles the C program given to `c.compile_and_run` with the object files to generate an executable binary. In this case, it generates binary `external_program` from `external_program.c` and `simple_math.o`. 
4. Finally, `external_program` is executed.

##### External C Program's Initialization
The external user's application must call the following functions to properly initialize and run the system:
- `init()` initializes states used by elements.
- `run_threads()` creates and runs normal pipelines.

Note that multiple pipelines can be compiled into one file; the file name is indicated by the parameter `process` when creating a pipeline. Therefore, a process/file can contains both normal and callable pipelines. In such case, it is crucial to call `run_threads()` in order to start running the normal pipelines.

**See xxx for an example.**


##### Default Return
If a callable pipeline has a return value, but the pipeline may not produce a return value because one or more elements in the pipeline may not fire its output ports, users have to provide a default return value to be used as the return value when the returning element of the API does not produce the return value. The default return value can be provided by assigning the default value to 
- the field `self.default_return = val` of the pipeline class, or
- the parameter `default_return` when instantiating the pipeline `pipeline_class(pipeline_name, default_return=val)`

**See xxx for an exmaple.**


### 3.3 run_order

If there are multiple source elements in a pipeline, we have to choose which source element is the starting element of the pipeline, and explicitly create dependency for the other source elements. For example, if we have `a >> b` and `c >> d`, and both `a` and `c` are source elements. We want `a` to be the starting element, and make `c` run after `b`. We can specify this intent using `run_order` as follows:
```python
class P(Pipeline):
  def impl(self):
     a >> b
     c >> d
     run_order(b, c)  # run b before c
```

In the scenario where there are multiple leaf nodes `l1`, `l1`, ..., `ln` reachable from the starting element, and only one of them will be executed per one packet, we write:
```python
run_order([l1, l2, ..., ln], c)  # run c after either l1, l2, .., or ln
```

### 3.4 Mapping to Device
By default, a pipeline is executed by one dedicated thread on a CPU. We can map a pipeline to a Cavium NIC by assinging the parameter `device` of the pipeline to `target.CAVIUM`: `pipeline_class(pipeline_name, device=target.CAVIUM)`

### 3.5 Mapping to Multiple Threads
By default, a pipeline is executed by one dedicated thread on a CPU, or one dedicated core on a Cavium NIC. We can run a pipeline on mutiple threads/cores in parallel by assigning parameter `cores` to a list of thread/core ids. For example, `pipeline_class(pipeline_name, device=target.CAVIUM, cores=[0,1,2,3])` runs this pipeline using cores 0--3 on Cavium.

On CPU, we can use an unlimited number of threads. Floem relies on an OS to schedule which threads to run. On Cavium, valid core ids are 0 to 11, as there are 12 cores on Cavium. Assigning the same core id to multiple pipelines leads to undefined behaviors.


## 4. State

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

### 4.1 Persistent State

State can be used as a global variable shared between multiple elements and persistent across all packets. Users must explicitly define which states an element can access to. Note that an element can access more than one states.

#### Example

```python
class Observer(Element):
  tracker = Persistent(Tracker)  # Define a state variable and its type.
  def states(self, tracker): 
    self.tracker = tracker       # Initialze a state variable.
  
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

### 4.2 Flow and Per-Packet State

Floem provides a per-packet state abstraction that a packet and its metadata can be accessed anywhere for the same *flow*. With this abstraction, programmers can access the per-packet state in any element without explicitly passing the per-packet state around. *Flow* is a set of pipelines that connect to each other via (queues)[#Multi-Queue].


To use this abstraction, programmers define a flow class, and set the field `state` of the flow class to a per-packet state associated with the flow. The elements and pipelines associated with the flow must be created inside the `impl` method of the flow. 

```python
class ProtocolBinaryReq(State):
    ...
    keylen = Field(Uint(16))
    extlen = Field(Uint(8))
    
class KVSmessage(State):
    ...
    mcr = Field(ProtocolBinaryReq)
    payload = Field(Array(Uint(8)))
    
class MyState(State):         
   pkt = Field(Pointer(KVSmessage))
   hash = Field(Uint(32))
   key = Field(Pointer(Uint(8)), size='state->pkt->mcr.keylen')  # variable-size field

class Main(Flow):             # define a flow
  state = PerPacket(MyState)  # associate per-packet state
  
  def impl(self):
    class Hash(Element):
      def configure(self):
        self.inp = Input(SizeT, Pointer(Void), Point(Void))  
        self.out = Ouput()    # no need to pass per-packet state
    
      def impl(self):
        self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        state->pkt = pkt;      // save pkt in a per-packet state
        uint8_t* key = state->pkt->payload + state->pkt->mcr.extlen;
        state->key = key;
        state->hash = hash(key, pkt->mcr.keylen);
        output { out(); }
        ''')
           
    class HashtGet(Element):
      ...
      def impl(self):
        self.run_c(r'''       // state refers to per-packet state
        state.it = hasht_get(state->key, state->pkt->mcr.keylen, state->hash);
        output { out(); }
        ''')
    ...
```

**See xxx as an example program.**

### 4.3 Special fields: layout, defined, packed
- `layout` By default, the defined fields in a state is laid out in an artitrary order in a struct. To control the order, we must explicitly assign the `layout` field of the state. 
- `packed` By default, Floem compiles a defined state to a C struct with `__attribute__ ((packed))`. In some cases, this is undesirable. For example, if the state contains a spin lock, we do not want the struct to be pakced. In such scenario, we can set the `packed` field to `False`.
- `defined` By default, Floem compiles a defined state to a C struct. However, if that struct has been defined in a C header file somewhere else that we include, we do not want to redefine the struct, but we still want to inform Floem about the struct so that it can reason about the per-packet state. In such case, we can set the `defined` field to `False` so that Floem will not generate code for the struct.

##### Example
```python
class MyState(State):         
   pkt = Field(Pointer(KVSmessage))
   hash = Field(Uint(32))
   key = Field(Pointer(Uint(8)), size='state->pkt->mcr.keylen')  # variable-size field
   layout = [pkt, hash, key]
   defined = False
   packed = False
```

## 5. Shared Data

### 5.1 Shared state between devices
If a state is used in elements that mapped to both a CPU and a NIC, a state will be allocated on host memory (CPU's memory), and the elements on the NIC must access the state via DMA operations.

For example,
```python
class Observer(Element):
  tracker = Persistent(Tracker)  # Define a state variable and its type.
  def states(self, tracker): 
    self.tracker = tracker       # Initialze a state variable.
  
  def configure(self):
    self.inp = Input(Int)   # Input port
    self.out = Output(Int)  # Output port
    
  def impl(self):           # Implementation for CPU
    self.run_c(r'''
      int id = inp();      // Retrieve a value from inp input port.
      tracker->total++;    // State is referenced as a pointer to a struct.
      tracker->last = id; 
      output { out(id); }
    ''')
    
  def impl_cavium(self):    # Implementation for Cavium NIC
    self.run_c(r'''
      int id = inp();      // Retrieve a value from inp input port.
      
      // Update tracker->total
      int *total;
      dma_read(&tracker->total, sizeof(int), &total);
      *total = *total + 1;
      dma_write(&tracker->total, sizeof(int), total, 1);  // 1 indicates blocking write
      
      // Update tracker->last
      int *last;
      dma_buf_alloc(&last);  // use dma_buf_alloc if we don't need the old content
      *last = id;
      dma_write(&tracker->last, sizeof(int), last, 1);
      
      dma_free(total); dma_free(last);
      output { out(id); }
    ''')
    
class P_CPU(Pipeline):
    def impl(self):
        o1 = Observer(states=[tracker1])  # observer element on CPU
        ...
        
class P_NIC(Pipeline):
    def impl(self):
        o2 = Observer(states=[tracker1])  # observer element on NIC
        ...
        
P_CPU(device=target.CPU)
P_NIC(device=target.NIC)
```
Note that if `impl_cavium` method is unimplementated, Floem uses `impl` method to generate code for both the CPU and the NIC.

### 5.2 Shared memory region
Floem provides another method for sharing a memory region between a CPU and a NIC or between different processes on a CPU without defining state. `MemoryRegion(<name>, <size_in_bytes>)` allocates a memory on host memory. `<name>`can be accessed by any element. For elements on a CPU, `<name>` is a local pointer to the shared region. For elements on a Cavium NIC, `<name>` is a physical address of the shared region, so we must use DMA operations to access the region. `<name>` can also be used in an external C program that includes the header filed generated by Floem.

**See `compiler/programas_perpacket_state/queue_shared_pointer.py` for a working example.** In this example, two external C programs (queue_shared_p1_main.c and queue_shared_p2_main.c) running in separate processes access the shared memory region called *data_region* created in Floem.

## 6. Multi-Queue

A multi-queue, or a logical queue, is a special kind of element. It differs from other elements in the sense that, once it receives a packet, it may not push the packet out to the next element right away; the packet is instead stored inside the queue until the dequeue is invoked. A queue is used to connect and send data from one pipeline to another, either between devices or within the same device. A queue connecting pipelines on the same device can be used as a temporary storage.

### 6.1 Primitive Queue

Floem supports two kinds of primitive multi-queues: a default queue and a custom queue.

##### A. Default Queue (not recommended as it is hard to use)
```python
import queue
queue.queue_default(name, entry_size, size, insts, checksum=False,
                    enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                    clean=False, qid_output=False)
return (EnqueueReserve, EnqueueSubmit, DequeueGet, DequeueRelease, clean_inst)
```
**Usage Summary**
*Enqueuing Routine:*
- Reserve an available queue entry (`EnqueueReserve`)
- Construct the queue entry in-place (user-defined elements)
- Submit the queue when finish constructing (`EnqueueSubmit`)
- Optionally, clean an old queue entry before enqueuing a new one (`clean_inst` and user-defined elements in its subgraph)
 
*Dequeuing Routine:*
- Get a ready queue entry (`DequeueGet`)
- Process the entry (user-defined elements)
- Release the entry (`DequeueRelease`)

**Requirements**
An entry of a default queue must be:
```python
def entry_t(State):
  flag = Field(Uint(8))
  task = Field(Uint(8))
  len  = Field(Uint(16))
  checksum = Field(Uint(8))
  pad  = Field(Uint(8))
  # and other fields for actual content
  layout = [flag, task, len, checksu, pad, ...]
```
or in C struct format:
```C
typedef struct {
    uint8_t flag;
    uint8_t task;
    uint16_t len;
    uint8_t checksum;
    uint8_t pad;
    // and other fields for actual content
} __attribute__((packed)) entry_t;
```
Users are responsible to fill in the content of an entry at the right location, and must not mutate the other fields except the task field.

**Parameters**
- `name`: name of the queue
- `entry_size`: maximum size of an entry in bytes. (For performance, entry_size should be 32 bytes or a multiple of 64 bytes.)
- `size`: number of entries in each physical queue instance
- `insts`: number of physical queue instances
- `checksum`: when `True`, checksum is enabled. **`checksum` must be set to `True` for a queue from a CPU to a Cavium NIC, whose `entry_size` > 64 bytes.**
- `enq_blocking`: when `True` the enqueue routine gaurantees to succesfully enqueue every entry, which requires blocking (waiting) when the queue is full.
- `deq_blocking`: when `True`, the dequeue routine always returns an entry with content. When `False`, it will returns NULL when the queue is empty.
- `enq_atomic`: when `True`, the enqueue routine is atomic. If multiple threads may enqueue to the same queue instance, `enq_atomic` should be set to `True`.
- `deq_atomic`: when `True`, the dequeue routine is atomic. If multiple threads may dequeue from the same queue instance, `deq_atomic` should be set to `True`.
- `clean`: when `True`, the enqueue routine cleans up an entry before enqueueing a new one.
- `qid_output`: when `True`, DequeueGet element class outputs qid.

**Returns**
`EnqueueReserve`: element class to reserve the next emptry entry.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry size (size_t) | size of entry (should not exceed queue's maximum entry size) |
|  |  | qid (size_t) | queue instance id (valid qids are 0 to `insts-1`) |
| out | output | entry_buffer (q_buffer) | queue entry with some metadata. entry_buffer.entry is a pointer to an actual entry. |

`EnqueueSubmit`: element class to submit a queue entry when finish filling in the content.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry_buffer (q_buffer) | queue entry |

`DequeueGet`: element class to get the next ready entry when `qid_output=False`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (size_t) | queue instance id |
| out | output | entry_buffer (q_buffer) | queue entry |

`DequeueGet`: element class to get the next ready entry when `qid_output=True`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (size_t) | queue instance id |
| out | output | entry_buffer (q_buffer) | queue entry |
|  |  | qid (size_t) | queue instance id |

`DequeueRelease`: element class to release a queue entry when working on the entry.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry_buffer (q_buffer) | queue entry |

`clean_inst`: element (not element class) that starts the process for cleaning a queue entry. The subgraph rooted at `clean_inst` is the cleaning routine.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| out | output | entry_buffer (q_buffer) | queue entry |

**Example Usage**
```python
import queue
EnqReserve, EnqSubmit, DeqGet, DeqRelease, clean = \
    queue.queue_default("myqueue", 32, 16, 4, clean=True)
    
'''
Creating enqueue function involves
1. reserve a queue entry (using EnqueueReserve)
2. fill the queue entry (using user-defined elements)
3. submit the queue entry (using EnqueueReserve)
4. cleaning the old entry (using clean). (This is optional.)
'''
class enqueue(CallablePipeline):
    def configure(self):
        self.inp  = Input(Int, SizeT)  # val, core

    def impl(self):
        # Create elements
        compute_core = ComputeCore(); fill_entry = FillEntry();
        enq_reserve = EnqReserve(); enq_submit = EnqSubmit();
        display = Display();
        
        # Enqueuing routine
        self.inp >> compute_core
        compute_core.size_qid >> enq_reserve >> fill_entry.size_qid
        compute_core.val >> fill_entry.size_qid
        fill_entry >> enq_submit

        # Cleaning routine (display old content before enqueuing a new entry)
        clean >> display
        
'''
Creating dequeue function involves
1. get a ready queue entry (using DequeueGet)
2. process the queue entry (using user-defined elements)
3. release the queue entry (using DequeueRelease)
'''
class dequeue(CallablePipeline):
    def configure(self):
        self.inp = Input(SizeT)

    def impl(self):
        self.inp >> DeqGet() >> Display() >> DequeueRelease()
```
**See `compile/programs/queue_variable_size.py` for a full example.**

##### B. Custom Queue

```python
import queue
queue.queue_custom(name, entry_type, size, insts, status_field, checksum=False,
                   enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                   enq_output=False)
return (Enqueue, DequeueGet, DequeueRelease)
```

**Usage Summary**
*Enqueuing Routine:*
- Construct a queue entry (user-defined elements)
- Copy the built queue entry into the queue (`Enqueue`)
 
*Dequeuing Routine:*
- Get a ready queue entry (`DequeueGet`)
- Process the entry (user-defined elements)
- Release the entry (`DequeueRelease`)

**Requirements**
Unlike that of the default queue, the fields of an entry of a custom queue is not fixed. However, the entry must meet the following requirements.
- An entry must contain a field (with any name) for storing an entry's status. This field should come after the other fields in an entry.
- If checksum is enabled, an entry must contain a field (with any name) of type uint8_t for storing checksum. This field should come after the status field.
- It is recommended for performance that an entry's size is 32 bytes or a multiple of 64 bytes. Therefore, if the struct/state representing an entry is not 32 bytes or a multiple of 64 bytes, it should be padded. The padding can come after the status and checksum fields.

**Parameters**
- `name`: name of the queue
- `entry_type`: entry type
- `size`: number of entries in each physical queue instance
- `insts`: number of physical queue instances
- `status_field`: name of the status field in an entry type
- `checksum`: name of the checksum field in an entry type. When `checksum` is `False`, checksum is disabled. **Checksum must be enabled for a queue from a CPU to a Cavium NIC, whose `entry_size` > 64 bytes.**
- `enq_blocking`: when `True` the enqueue routine gaurantees to succesfully enqueue every entry, which requires blocking (waiting) when the queue is full.
- `deq_blocking`: when `True`, the dequeue routine always returns an entry with content. When `False`, it will returns NULL when the queue is empty.
- `enq_atomic`: when `True`, the enqueue routine is atomic. If multiple threads may enqueue to the same queue instance, `enq_atomic` should be set to `True`.
- `deq_atomic`: when `True`, the dequeue routine is atomic. If multiple threads may dequeue from the same queue instance, `deq_atomic` should be set to `True`.
- `enq_output`: when `True`, `Enqueue` element class outputs the entry being copied to the queue.

**Returns**
`Enqueue`: element class to copy a queue entry into a queue when `enq_output=False`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry pointer (entry_type *) | pointer to a queue entry |
|  |  | qid (size_t) | queue instance id |

`Enqueue`: element class to copy a queue entry into a queue when `enq_output=True`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry pointer (entry_type *) | pointer to a queue entry |
|  |  | qid (size_t) | queue instance id |
| done | output | entry pointer (entry_type *) | pointer to a queue entry (same as the input entry pointer) |

`DequeueGet`: element class to get the next ready entry.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (size_t) | queue instance id |
| out | output | entry_buffer (q_buffer) | queue entry |

`DequeueRelease`: element class to release a queue entry when working on the entry.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry_buffer (q_buffer) | queue entry |

**Example Usage**
```python
import queue

class Tuple(State):
    val = Field(Int)
    task = Field(Uint(8))
    layout = [val, task]
    
Enq, Deq, Release = queue.queue_custom('myqueue', Tuple, 16, 4, Tuple.task)

class enqueue(CallablePipeline):
    def configure(self):
        self.inp = Input(Pointer(Tuple), SizeT)

    def impl(self):
        self.inp >> Enq()

class dequeue(CallablePipeline):
    def configure(self):
        self.inp = Input(SizeT)

    def impl(self):
        self.inp >> Deq() >> Display() >> Release()
```
If we need to do a post processing on a queue entry after enqueuing, we can set `enq_output=True` as follows:
```python
Enq, Deq, Release = queue.queue_custom('myqueue', Tuple, 16, 4, Tuple.task, enq_output=True)

class enqueue(CallablePipeline):
    ...
    def impl(self):
        self.inp >> Enq() >> PostEnq() >> ...
```
Note that if `enq_blocking=False` and the queue is full, `Enq` will still output the pointer to an entry although it does not succesfully copy the entry into the queue.

### 6.2 Smart Queue
Smart queue can be used within a [flow and per-packet state](#Flow). Unlike the primitive queue, users do not have to explicitly define the queue entry type. Floem infers which fields in the per-packet state need to be sent to the other side of the queue. Users also do not have to release a queue entry manually. Internally, Floem transforms a smart queue to a [default queue](#Default-Queue) and inserts elements to release a queue entry as earliest as it can.

```python
import queue_smart
queue_smart.smart_queue(name, entry_size, size, insts, channels, checksum=False,
                        enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False, 
                        enq_output=False, clean=False)
return Enqueue, Dequeue, Clean
```

**Requirements**
- It is recommended for performance that an entry's size is 32 bytes or a multiple of 64 bytes. 
- `Enqueue` element class does not explicitly takes qid as an input. Users must assign `state->qid` inside any element that is executed before `Enqueue`.

**Parameters**
- `name`: name of the queue
- `entry_size`: maximum size of an entry in bytes. (For performance, entry_size should be 32 or a multiple of 64 bytes.)
- `size`: number of entries in each physical queue instance
- `insts`: number of physical queue instances
- `channels`: number of virtual channels (number of connections between the pipelines connected by the queue)
- `checksum`: when True, checksum is enabled. **`checksum` must be set to True for a queue from a CPU to a Cavium NIC, whose entry_size > 64 bytes.**
- `enq_blocking`: when `True` the enqueue routine gaurantees to succesfully enqueue every entry, which requires blocking (waiting) when the queue is full.
- `deq_blocking`: when `True`, the dequeue routine always returns an entry with content. When `False`, it will returns NULL when the queue is empty.
- `enq_atomic`: when `True`, the enqueue routine is atomic. If multiple threads may enqueue to the same queue instance, `enq_atomic` should be set to `True`.
- `deq_atomic`: when `True`, the dequeue routine is atomic. If multiple threads may dequeue from the same queue instance, `deq_atomic` should be set to `True`.
- `enq_output`: when `True`, `Enqueue` element class outputs the entry being copied to the queue.
- `clean`: when `True`, the enqueue routine cleans up an entry before enqueueing a new one.
- 
**Returns**
`Enqueue`: element class to enqueue a per-packet state to a queue when `enq_output=False`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp[i] | input | none |  |

`Enqueue`: element class to enqueue a per-packet state to a queue when `enq_output=True`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp[i] | input | none |  |
| done | output | none | |

`Dequeue`: element class to enqueue a per-packet state from a queue.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (size_t) | queue instance id |
| out[i] | output | none | |

`Clean`: element class that starts the process for cleaning a queue entry. The subgraph of starting from this element is the cleaning routine.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| out[i] | output | none | |

i = 0 to `channels-1`.

**Example Usage**
```python
import queue_smart

class MyState(State):
    type = Field(Int)
    a = Field(Int)
    b = Field(Int)
    qid = Field(Int)
    
class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        Enq, Deq, Clean = queue_smart.smart_queue("queue", 32, 16, 4, channels=2)

        class run1(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                save = Save()
                classify = Classify()
                enq = Enq()

                self.inp >> save >> classify
                classify.out1 >> A0() >> enq.inp[0]  # A0 defines state->a (channel 0)
                classify.out2 >> B0() >> enq.inp[1]  # B0 defines state->b (channel 1)

        class run2(CallablePipeline):
            def configure(self):
                self.inp = Input(SizeT)

            def impl(self):
                deq = Deq()

                self.inp >> deq
                deq.out[0] >> A1()                   # A0 users state->a (channel 0)
                deq.out[1] >> B1()                   # A0 users state->b (channel 1)

        run1('run1')
        run2('run2')
```

##### Variable-size field
When a variable-size field is sent over a queue, the compiler needs the information about the size of the field. Users must inform the compiler by annotating the `size` parameter of `Field`. For example, 
```python
class MyState(State):         
   pkt = Field(Pointer(KVSmessage))
   key = Field(Pointer(Uint(8)), size='state->pkt->mcr.keylen')  # variable-size field
```

##### Pointer to shared memory region
When a pointer to a [shared memory region](#Shared-Memory-Region) it sent over a queue, the compiler needs to convert the address value with respect to the process's and the device's address space. Users must infrom the compiler if a particular field is a pointer to which shared memory region. For example, 
```python
class MyState(State):
    p = Field(Pointer(Int), shared='data_region')  # a pointer to shared memory region 'data_region'
```

##### Field Granularity
Floem attempts to send the least amount of data across a field with respect to the information provided by the users. For example, assume that the field `state->pkt->mcr.keylen` needs to be sent over a queue.

The compiler will send just the `keylen` field, if the users define a per-packet state as follows:
```python
class ProtocolBinaryReq(State):
    ...
    keylen = Field(Uint(16))
    
class KVSmessage(State):
    ...
    mcr = Field(ProtocolBinaryReq)
    
class MyState(State):         
   pkt = Field(Pointer(KVSmessage))

class Main(Flow):
  state = PerPacket(MyState)  # per-packet state
```

However, if the users decide to define `KVSmessage` in a C header file that is included into a Floem program, and define a per-packet state as below. The compiler will send the entire `pkt` field as supposed to just the `keylen` field because it does not have information about the `keylen` field.
```python
class MyState(State):         
   pkt = Field('KVSmessage *')

class Main(Flow):
  state = PerPacket(MyState)  # per-packet state
```

##### Byte order
x86 is little-endian, while Cavium LiquidIO is big-endian. When using a smart queue, the compiler will automatically convert the byte order on the NIC side for the fields that use provided data types. Users are responsible for converting the byte order manually when using primitive queues.

## 7. Network Elements
```python
import net
```
### FromNet

### FromNetFree

### NetAlloc

### ToNet

### Example

## 8. Other Library Elements
```python
import library
```

## 9. Composite Element

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

## 11. Example Application: Memcached
## 12. Example Application: Storm

# C. Running on Cavium

# D. Compiler's Options

