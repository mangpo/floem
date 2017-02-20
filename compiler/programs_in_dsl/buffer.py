from dsl import *

Buffer = create_state("Buffer", "int x; int avail;", [0,0])
Write = create_element("Write",
                       [Port("in", ["int"])],
                       [],
                       r'''if(this.avail==1) { printf("Failed.\n"); exit(-1); } this.x = in(); this.avail = 1;''',
                       None,
                       [("Buffer", "this")])
BlockingRead = create_element("BlockingRead",
                              [],
                              [],
                              r'''while(this.avail==0); int x = this.x; this.avail = 0; printf("%d\n", x);''',
                              None,
                              [("Buffer", "this")])

buffer = Buffer()
write = Write("w", [buffer])
read = BlockingRead("r", [buffer])

c =Compiler()
c.testing = "w(42); r(); w(123); r();";
c.generate_code_and_run([42, 123])