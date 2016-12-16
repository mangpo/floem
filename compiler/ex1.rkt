#lang racket

(require "connector.rkt")

(define file (open-output-file "temp.py" #:exists 'replace))
(parameterize ([current-output-port file])

(Element 'Fork
         [input (port 'in '(int int))]
         [output (port 'to_add '(int))
                 (port 'to_sub '(int))]
         [run "(int x, int y) = in(); to_add(x,y); to_sub(x,y);"])

(Element 'Add
        [input (port 'in '(int int))]
        [output (port 'out '(int))]
        [run "(int x, int y) = in(); out(x+y);"])

(Element 'Sub
        [input (port 'in '(int int))]
        [output (port 'out '(int))]
        [run "(int x, int y) = in(); out(x-y);"])

(Element 'Print
         [input (port 'in '(int))]
         [run "printf(\"%d\\n\",in());"])

(define-elements)
(Instance fork 'Fork)
(Instance add 'Add)
(Instance sub 'Sub)
(Instance print 'Print)

(Pipeline fork (out 'to_add) add print) ; fork [to_add] >> add >> print
(Pipeline fork (out 'to_sub) sub print) ; fork [to_sub] >> sub >> print
(generate-code)
  )


(close-output-port file)
(system "python temp.py")
