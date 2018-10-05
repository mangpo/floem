# Library of Elements

1. [Queue](#Multi-Queue)
2. [Network Elements](#Network-Elements)
3. [Other Library Elements](#Other-Library-Elements)

<a name="Multi-Queue"></a>
## 1. Queue

A queue is used to connect and send data from one segment to another, 
either between devices or within the same device. 
A queue connecting segments on the same device can be used as 
a temporary storage.

### 1.1 Primitive Queue (not recommended as it is hard to use)

Floem supports two kinds of primitive queues: a default queue and a custom queue.

##### A. Default Queue
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
| inp | input | entry size (int) | size of entry (should not exceed queue's maximum entry size) |
|     |       | qid (int) | queue instance id (valid qids are 0 to `insts-1`) |
| out | output | entry_buffer (q_buffer) | queue entry with some metadata. entry_buffer.entry is a pointer to an actual entry. |

`EnqueueSubmit`: element class to submit a queue entry when finish filling in the content.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry_buffer (q_buffer) | queue entry |

`DequeueGet`: element class to get the next ready entry when `qid_output=False`.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (int) | queue instance id |
| out | output | entry_buffer (q_buffer) | queue entry |

`DequeueGet`: element class to get the next ready entry when `qid_output=True`.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (int) | queue instance id |
| out | output | entry_buffer (q_buffer) | queue entry |
|  |  | qid (int) | queue instance id |

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
class enqueue(CallableSegment):
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
class dequeue(CallableSegment):
    def configure(self):
        self.inp = Input(SizeT)

    def impl(self):
        self.inp >> DeqGet() >> Display() >> DequeueRelease()
```
> See `floem/programs/queue_default.py` for a complete example.

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
|  |  | qid (int) | queue instance id |

`Enqueue`: element class to copy a queue entry into a queue when `enq_output=True`.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | entry pointer (entry_type *) | pointer to a queue entry |
|  |  | qid (int) | queue instance id |
| done | output | entry pointer (entry_type *) | pointer to a queue entry (same as the input entry pointer) |

`DequeueGet`: element class to get the next ready entry.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | qid (int) | queue instance id |
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

class enqueue(CallableSegment):
    def configure(self):
        self.inp = Input(Pointer(Tuple), SizeT)

    def impl(self):
        self.inp >> Enq()

class dequeue(CallableSegment):
    def configure(self):
        self.inp = Input(SizeT)

    def impl(self):
        self.inp >> Deq() >> Display() >> Release()
```
If we need to do a post processing on a queue entry after enqueuing, we can set `enq_output=True` as follows:
```python
Enq, Deq, Release = queue.queue_custom('myqueue', Tuple, 16, 4, Tuple.task, enq_output=True)

class enqueue(CallableSegment):
    ...
    def impl(self):
        self.inp >> Enq() >> PostEnq() >> ...
```
Note that if `enq_blocking=False` and the queue is full, `Enq` will still output the pointer to an entry although it does not succesfully copy the entry into the queue.

> See `floem/programs/queue_custom.py` for a complete example.

### 1.2 Smart Queue (recommended)
Smart queue can be used within a [flow and per-packet state](../README.md#Flow). 
Unlike the primitive queue, users do not have to explicitly define 
the queue entry type. Floem infers which fields in the per-packet state 
need to be sent to the other side of the queue. Users also do not 
have to release a queue entry manually. Internally, Floem transforms 
a smart queue to a [default queue](../README.md#Default-Queue) and 
inserts elements to release a queue entry as earliest as it can.

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
- `channels`: number of logical channels (number of connections between the segments connected by the queue)
- `checksum`: when True, checksum is enabled. **`checksum` must be set to True for a queue from a CPU to a Cavium NIC, whose entry_size > 64 bytes.**
- `enq_blocking`: when `True` the enqueue routine gaurantees to succesfully enqueue every entry, which requires blocking (waiting) when the queue is full.
- `deq_blocking`: when `True`, the dequeue routine always returns an entry with content. When `False`, it will returns NULL when the queue is empty.
- `enq_atomic`: when `True`, the enqueue routine is atomic. If multiple threads may enqueue to the same queue instance, `enq_atomic` should be set to `True`.
- `deq_atomic`: when `True`, the dequeue routine is atomic. If multiple threads may dequeue from the same queue instance, `deq_atomic` should be set to `True`.
- `enq_output`: when `True`, `Enqueue` element class outputs the entry being copied to the queue.
- `clean`: when `True`, the enqueue routine cleans up an entry before enqueueing a new one.

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
| inp | input | qid (int) | queue instance id |
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

        class run1(CallableSegment):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                save = Save()
                classify = Classify()
                enq = Enq()

                self.inp >> save >> classify
                classify.out1 >> A0() >> enq.inp[0]  # A0 defines state->a (channel 0)
                classify.out2 >> B0() >> enq.inp[1]  # B0 defines state->b (channel 1)

        class run2(CallableSegment):
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

> See `floem/programs/smart_queue_entry_simple.py` for a complete example.

When `enq_output=True`, `enq.done` must be connected to an element `e`. 
`e` and its subsequent elements are executed immediately after an entry 
is enqueued. Often, this feature is used with 
[`FromNetFree`](#FromNetFree) element for freeing a packet buffer when 
packet content has been copied into a queue.

When `clean=True`, element `clean = Clean()` must be connected to 
an element `e`.  `e` and its subsequent elements are for cleaning 
an entry that has been done processing (after dequeue release) 
on the sender's side. `e` and its subsequent elements must be 
in the same segment as an instance of `Enqueue`. They are executed 
immediately before a new entry is being enqueued. 

> See `floem/programs/smart_queue_entry.py` for an example with `enq_output=True` and `clean=True`.

##### Pointer to shared memory region
When a pointer to a [shared memory region](../README.md#Shared-Memory-Region) it sent over a queue, the compiler needs to convert the address value with respect to the process's and the device's address space. Users must inform the compiler if a particular field is a pointer to which shared memory region. For example, 
```python
class MyState(State):
    p = Field(Pointer(Int), shared='data_region')  # a pointer to shared memory region 'data_region'
```
> See `compile/programs_perpacket_state/queue_shared_pointer.py` for a working example.

##### Variable-size field
When a variable-size field is sent over a queue, the compiler needs the information about the size of the field. Users must inform the compiler by annotating the `size` parameter of `Field`. For example, 
```python
class MyState(State):         
   pkt = Field(Pointer(KVSmessage))
   key = Field(Pointer(Uint(8)), size='state->pkt->mcr.keylen')  # variable-size field
```

> See `floem/programs_perpacket_state/queue_shared_data.py` for a working example.

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

<a name="Network-Elements"></a>
## 2. Network Elements
```python
import net
```

`net.FromNet(configure=[batch_size])`: element to get a packet from the network. This element fires `out` port if there are packets in the ingress buffer; otherwise it fires `nothing` port. Default `batch_size` is 32. Chaniging `batch_size` will not change the behavior of the program, it is for performance tuning.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| out | output | size (size_t) | packet's size in bytes |
|  |  | packet pointer (void *) | pointer to a packet |
|  |  | buffer pointer (void *) | pointer to a packet's buffer |
| nothing | output | none | |

`net.NetAlloc()`: element to allocate a buffer for building a packet. This element fires `out` port if it successfully allocates a packet's buffer; otherwise, it fires `oom` port (out of memory).

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | size (size_t) | packet's size in bytes |
| out | output | size (size_t) | packet's size in bytes |
|  |  | packet pointer (void *) | pointer to an allocated packet |
|  |  | buffer pointer (void *) | pointer to an allocated packet's buffer |
| oom | output | none |  |

`net.ToNet(configure=[source, batch_size])`: element to send a packet to the network. `source` should be either "from_net" (the input packet is from FromNet element) or "net_alloc" (the input packet is not from FromNet element). Default `source` is "from_net". Default `batch_size` is 32.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | size (size_t) | packet's size in bytes |
|  |  | packet pointer (void *) | pointer to a packet |
|  |  | buffer pointer (void *) | pointer to a packet's buffer |

<a name="FromNetFree"></a>
`net.FromNetFree()`: element to free a packet's buffer created from FromNet element. Users must use this element if a packet from FromNet does not flow to ToNet elemnet.

| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | packet pointer (void *) | pointer to a packet |
|  |  | buffer pointer (void *) | pointer to a packet's buffer |

> See `apps/benchmarks/reply.py` for a basic working example.
> See `apps/storm/main_dccp.py` for a more sophisticated working example.

<a name="Other-Library-Elements"></a>
## 3. Other Library Elements
```python
import library
```
`library.Drop()`: element to drop anything that comes in.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| inp | input | none |  |
 As described earlier, an input port with zero argument, like this input port, can be connected from an output port with any number of arguments of any data types.
 
`library.Constant(configure=[data_type,const])`: element that produces a constant. `data_type` is the data type of the constant `const`.
| Port | Port type | Argument (datatype) | Argument description |
| ------ | ------ | ------ | ------ |
| out | output | const (`data_type`) | the given constant `const` |

See all provided elements in `floem/library.py`.

