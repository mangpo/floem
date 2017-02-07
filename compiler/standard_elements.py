from graph import Element, Port

Fork2 = Element("Fork2",
                [Port("in", ["int"])],
                [Port("out1", ["int"]), Port("out2", ["int"])],
                r'''(int x) = in(); output { out1(x); out2(x); }''')
Fork3 = Element("Fork3",
                [Port("in", ["int"])],
                [Port("out1", ["int"]), Port("out2", ["int"]), Port("out3", ["int"])],
                r'''(int x) = in(); output { out1(x); out2(x); out3(x); }''')
Forward = Element("Forward",
                  [Port("in", ["int"])],
                  [Port("out", ["int"])],
                  r'''int x = in(); output { out(x); }''')
Add = Element("Add",
              [Port("in1", ["int"]), Port("in2", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in1() + in2(); output { out(x); }''')

Inc = Element("Inc",
              [Port("in", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in() + 1; output { out(x); }''')