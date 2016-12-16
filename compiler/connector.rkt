#lang racket

(provide Element Instance Pipeline
         define-elements generate-code
         (struct-out port) (struct-out in) (struct-out out))

(struct element (name in out code))
(struct port (name types))
(struct out (name))
(struct in (name))

(define all-elements (make-hash))

(define-syntax Element
  (syntax-rules (input output run)

    ((Element e
              [input in ...]
              [output out ...]
              [run code])
     (hash-set! all-elements
                e
                (element e
                         (list in ...)
                         (list out ...)
                         code)))

    ((Element e
              [input in ...]
              [run code])
     (Element e [input in ...] [output] [run code]))
    
    ))

(define (define-elements)
  (pretty-display "from ast import *")
  (pretty-display "from compiler import Compiler")
  (define names
    (for/list ([e (hash-values all-elements)])
      (print-element e)))

  (pretty-display (format "compiler = Compiler([~a])" (string-join names ","))))

(define id 0)
(define (print-element e)
  (define name (format "e~a" id))
  (set! id (add1 id))

  (define ins (string-join (map string-port (element-in e)) ","))
  (define outs (string-join (map string-port (element-out e)) ","))

  (pretty-display (format "~a = Element(\"~a\", [~a], [~a], r'''~a''')"
                          name (element-name e) ins outs (element-code e)))
  name)

(define (string-port p)
  (format "Port(\"~a\", [~a])"
          (port-name p)
          (string-join
           (map (lambda (x) (format "\"~a\"" x)) (port-types p))
           ",")))

(define-syntax-rule (Instance e type)
  (define e
    (begin
      (pretty-display (format "compiler.defineInstance(\"~a\", \"~a\")" type type))
      type)))

(define-syntax-rule (Pipeline e ...)
  (pipeline (list e ...)))

(define (pipeline es)
  (when (>= (length es) 2)
    (cond
      [(out? (second es)) (pipeline (cons (cons (first es) (second es))
                                         (drop es 2)))]
      [(in? (second es)) (pipeline (append (list (first es)
                                                (cons (third es) (second es)))
                                          (drop es 3)))]
      [else (connect (first es) (second es))
            (if (pair? (second es))
                (pipeline (cons (first (second es)) (drop es 2)))
                (pipeline (cdr es)))])))

(define (connect a b)
  (cond
    [(and (pair? a) (pair? b))
     (pretty-display (format "compiler.connect(\"~a\", \"~a\", \"~a\", \"~a\")"
                              (car a) (car b) (out-name (cdr a)) (in-name (cdr b))))]
    [(pair? a)
     (pretty-display (format "compiler.connect(\"~a\", \"~a\", \"~a\")"
                              (car a) b (out-name (cdr a))))]

    [else
     (pretty-display (format "compiler.connect(\"~a\", \"~a\")"
                              a b))]))

(define (generate-code)
  (pretty-display "compiler.generateCode()"))
     
