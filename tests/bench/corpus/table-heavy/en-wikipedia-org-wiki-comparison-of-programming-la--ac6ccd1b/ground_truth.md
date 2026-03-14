# Comparison of programming languages (basic instructions)


This article needs additional citations for .
(February 2009) |

This article compares a large number of [programming languages](https://en.wikipedia.org/wiki/Programming_language) by tabulating their [data types](https://en.wikipedia.org/wiki/Data_type), their [expression](https://en.wikipedia.org/wiki/Expression_(computer_science)), [statement](https://en.wikipedia.org/wiki/Statement_(computer_science)), and [declaration](https://en.wikipedia.org/wiki/Declaration_(computer_programming)) [syntax](https://en.wikipedia.org/wiki/Syntax_(programming_languages)), and some common operating-system interfaces.

## Conventions of this article

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=1)]

Generally, *var*, `var`, or `var` is how variable names or other non-literal values to be interpreted by the reader are represented. The rest is literal code. [Guillemets](https://en.wikipedia.org/wiki/Guillemet) (`«`

and `»`

) enclose optional sections. `Tab ↹` indicates a necessary (whitespace) indentation.

The tables are not sorted lexicographically ascending by programming language name by default, and that some languages have entries in some tables but not others.

## Type identifiers

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=2)]

| 8 bit (
|
|---|

[short integer](https://en.wikipedia.org/wiki/Short_integer))

[long integer](https://en.wikipedia.org/wiki/Long_integer))

[bignum](https://en.wikipedia.org/wiki/Arbitrary-precision_arithmetic))

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`range -2**7 .. 2**7 - 1`

[[j]](https://en.wikipedia.org#endnote_Ada_range)`range 0 .. 2**8 - 1`

or[[j]](https://en.wikipedia.org#endnote_Ada_range)`mod 2**8`

[[k]](https://en.wikipedia.org#endnote_Ada_mod)`range -2**15 .. 2**15 - 1`

[[j]](https://en.wikipedia.org#endnote_Ada_range)`range 0 .. 2**16 - 1`

or[[j]](https://en.wikipedia.org#endnote_Ada_range)`mod 2**16`

[[k]](https://en.wikipedia.org#endnote_Ada_mod)`range -2**31 .. 2**31 - 1`

[[j]](https://en.wikipedia.org#endnote_Ada_range)`range 0 .. 2**32 - 1`

or[[j]](https://en.wikipedia.org#endnote_Ada_range)`mod 2**32`

[[k]](https://en.wikipedia.org#endnote_Ada_mod)`range -2**63 .. 2**63 - 1`

[[j]](https://en.wikipedia.org#endnote_Ada_range)`mod 2**64`

[[k]](https://en.wikipedia.org#endnote_Ada_mod)`Integer`

[[j]](https://en.wikipedia.org#endnote_Ada_range)`range 0 .. 2**Integer'Size - 1`

or[[j]](https://en.wikipedia.org#endnote_Ada_range)`mod Integer'Size`

[[k]](https://en.wikipedia.org#endnote_Ada_mod)[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)(variable-width)`short short int`

[[c]](https://en.wikipedia.org#endnote_CInt)`short int`

[[c]](https://en.wikipedia.org#endnote_CInt)`int`

[[c]](https://en.wikipedia.org#endnote_CInt)`long int`

[[c]](https://en.wikipedia.org#endnote_CInt)`int`

[[c]](https://en.wikipedia.org#endnote_CInt)`long long int`

[[a]](https://en.wikipedia.org#endnote_a68)[[g]](https://en.wikipedia.org#endnote_a68g)`bytes`

and `bits`

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99)fixed-width)`int8_t`

`uint8_t`

`int16_t`

`uint16_t`

`int32_t`

`uint32_t`

`int64_t`

`uint64_t`

`intptr_t`

[[c]](https://en.wikipedia.org#endnote_CInt)`size_t`

[[c]](https://en.wikipedia.org#endnote_CInt)[C++](https://en.wikipedia.org/wiki/C%2B%2B)([C++11](https://en.wikipedia.org/wiki/C%2B%2B11)fixed-width)[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99)variable-width)`signed char`

`unsigned char`

, `byte`

([C++17](https://en.wikipedia.org/wiki/C%2B%2B17))`short`

[[c]](https://en.wikipedia.org#endnote_CInt)`unsigned short`

[[c]](https://en.wikipedia.org#endnote_CInt)`long`

[[c]](https://en.wikipedia.org#endnote_CInt)`unsigned long`

[[c]](https://en.wikipedia.org#endnote_CInt)`long long`

[[c]](https://en.wikipedia.org#endnote_CInt)`unsigned long long`

[[c]](https://en.wikipedia.org#endnote_CInt)`int`

[[c]](https://en.wikipedia.org#endnote_CInt)`unsigned int`

[[c]](https://en.wikipedia.org#endnote_CInt)[C++](https://en.wikipedia.org/wiki/C%2B%2B)([C++11](https://en.wikipedia.org/wiki/C%2B%2B11)variable-width)[Objective-C](https://en.wikipedia.org/wiki/Objective-C)([Cocoa](https://en.wikipedia.org/wiki/Cocoa_(API)))`signed char`

or `int8_t`

`unsigned char`

or `uint8_t`

`short`

or `int16_t`

`unsigned short`

or `uint16_t`

`int`

or `int32_t`

`unsigned int`

or `uint32_t`

`long long`

or `int64_t`

`unsigned long long`

or `uint64_t`

`NSInteger`

or `long`

`NSUInteger`

or `unsigned long`

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`sbyte`

`byte`

`short`

`ushort`

`int`

`uint`

`long`

`ulong`

`IntPtr`

`UIntPtr`

`System.Numerics.`BigInteger

(.NET 4.0)

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`byte`

`char`

[[b]](https://en.wikipedia.org#endnote_Java_char)`java.math.`BigInteger

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`int8`

`uint8`

or `byte`

`int16`

`uint16`

`int32`

`uint32`

`int64`

`uint64`

`int`

`uint`

`big.Int`

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`i8`

`u8`

`i16`

`u16`

`i32`

`u32`

`i64`

`u64`

`isize`

`usize`

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`Int8`

`UInt8`

`Int16`

`UInt16`

`Int32`

`UInt32`

`Int64`

`UInt64`

`Int`

`UInt`

[D](https://en.wikipedia.org/wiki/D_(programming_language))`byte`

`ubyte`

`short`

`ushort`

`int`

`uint`

`long`

`ulong`

`BigInt`

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)[[2]](https://en.wikipedia.org#cite_note-HyperSpec-2)`(signed-byte 8)`

`(unsigned-byte 8)`

`(signed-byte 16)`

`(unsigned-byte 16)`

`(signed-byte 32)`

`(unsigned-byte 32)`

`(signed-byte 64)`

`(unsigned-byte 64)`

`bignum`

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[[3]](https://en.wikipedia.org#cite_note-Specification-3)`bignum`

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))([FPC](https://en.wikipedia.org/wiki/Free_Pascal))`shortint`

`byte`

`smallint`

`word`

`longint`

`longword`

`int64`

`qword`

`integer`

`cardinal`

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Byte`

`Integer`

`Long`

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`SByte`

`Short`

`UShort`

`Integer`

`UInteger`

`Long`

`ULong`

`System.Numerics`.BigInteger

(.NET 4.0)

[FreeBasic](https://en.wikipedia.org/wiki/FreeBasic)`Byte`

or `Integer<8>`

`UByte`

or `UInteger<8>`

`Short`

or `Integer<16>`

`UShort`

or `UInteger<16>`

`Long`

or `Integer<32>`

`ULong`

or `UInteger<32>`

`LongInt`

or `Integer<64>`

`ULongInt`

or `UInteger<64>`

`Integer`

`UInteger`

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))2.x`int`

`long`

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))3.x`int`

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)[Fortran](https://en.wikipedia.org/wiki/Fortran)`INTEGER(KIND = n)`

[[f]](https://en.wikipedia.org#endnote_Kinds)`INTEGER(KIND = n)`

[[f]](https://en.wikipedia.org#endnote_Kinds)`INTEGER(KIND = n)`

[[f]](https://en.wikipedia.org#endnote_Kinds)`INTEGER(KIND = n)`

[[f]](https://en.wikipedia.org#endnote_Kinds)[PHP](https://en.wikipedia.org/wiki/PHP)`int`

[[m]](https://en.wikipedia.org#endnote_PHP_32/64_bit_long)`int`

[[m]](https://en.wikipedia.org#endnote_PHP_32/64_bit_long)[[e]](https://en.wikipedia.org#endnote_PHP_bignum)[Perl](https://en.wikipedia.org/wiki/Perl)5[[d]](https://en.wikipedia.org#endnote_scalars)[[d]](https://en.wikipedia.org#endnote_scalars)[[d]](https://en.wikipedia.org#endnote_scalars)[[d]](https://en.wikipedia.org#endnote_scalars)[[d]](https://en.wikipedia.org#endnote_scalars)`Math::BigInt`

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`int8`

`uint8`

`int16`

`uint16`

`int32`

`uint32`

`int64`

`uint64`

`Int`

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`Fixnum`

`Bignum`

[Erlang](https://en.wikipedia.org/wiki/Erlang_(programming_language))[[n]](https://en.wikipedia.org#endnote_Erlang_int)`integer()`

`integer()`

[[o]](https://en.wikipedia.org#endnote_Erlang_arb)[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`Byte`

`Short`

`Char`

[[l]](https://en.wikipedia.org#endnote_Scala_Char)`Int`

`Long`

`scala.math.BigInt`

[Seed7](https://en.wikipedia.org/wiki/Seed7)`integer`

`bigInteger`

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)`SmallInteger`

[[i]](https://en.wikipedia.org#endnote_Smalltalk)`LargeInteger`

[[i]](https://en.wikipedia.org#endnote_Smalltalk)[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)[OCaml](https://en.wikipedia.org/wiki/OCaml)`int32`

`int64`

`int`

or `nativeint`

`open Big_int;;`

or `big_int`

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`sbyte`

`byte`

`int16`

`uint16`

`int32`

or `int`

`uint32`

`uint64`

`nativeint`

`unativeint`

`bigint`

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`Word8.word`

`Int32.int`

`Word32.word`

`Int64.int`

`Word64.word`

`int`

`word`

`LargeInt.int`

or`IntInf.int`

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`«import Int»`

or `Int8`

`«import Word»`

or `Word8`

`«import Int»`

or `Int16`

`«import Word»`

or `Word16`

`«import Int»`

or `Int32`

`«import Word»`

or `Word32`

`«import Int»`

or `Int64`

`«import Word»`

or `Word64`

`Int`

`«import Word»`

or `Word`

`Integer`

[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))`INTEGER_8`

`NATURAL_8`

`INTEGER_16`

`NATURAL_16`

`INTEGER_32`

`NATURAL_32`

`INTEGER_64`

`NATURAL_64`

`INTEGER`

`NATURAL`

[COBOL](https://en.wikipedia.org/wiki/COBOL)[[h]](https://en.wikipedia.org#endnote_Cobol)`BINARY-CHAR «SIGNED»`

`BINARY-CHAR UNSIGNED`

`BINARY-SHORT «SIGNED»`

`BINARY-SHORT UNSIGNED`

`BINARY-LONG «SIGNED»`

`BINARY-LONG UNSIGNED`

`BINARY-DOUBLE «SIGNED»`

`BINARY-DOUBLE UNSIGNED`

[Mathematica](https://en.wikipedia.org/wiki/Mathematica)`Integer`

[Wolfram Language](https://en.wikipedia.org/wiki/Wolfram_Language)`Integer`

The[^a](https://en.wikipedia.org#ref_a68)*standard*constants`int shorts`

and`int lengths`

can be used to determine how many`short`

s and`long`

s can be usefully prefixed to`short int`

and`long int`

. The actual sizes of`short int`

,`int`

, and`long int`

are available as the constants`short max int`

,`max int`

, and`long max int`

etc.Commonly used for characters.[^b](https://en.wikipedia.org#ref_Java_char)The ALGOL 68, C and C++ languages do not specify the exact width of the integer types[^c](https://en.wikipedia.org#ref_CInt)`short`

,`int`

,`long`

, and ([C99](https://en.wikipedia.org/wiki/C99),[C++11](https://en.wikipedia.org/wiki/C%2B%2B11))`long long`

, so they are implementation-dependent. In C and C++`short`

,`long`

, and`long long`

types are required to be at least 16, 32, and 64 bits wide, respectively, but can be more. The`int`

type is required to be at least as wide as`short`

and at most as wide as`long`

, and is typically the width of the word size on the processor of the machine (i.e. on a 32-bit machine it is often 32 bits wide; on 64-bit machines it is sometimes 64 bits wide).[C99](https://en.wikipedia.org/wiki/C99)and[C++11](https://en.wikipedia.org/wiki/C%2B%2B11)[also define the][citation needed](https://en.wikipedia.org/wiki/Wikipedia:Citation_needed)`[u]intN_t`

exact-width types in the[stdint.h](https://en.wikipedia.org/wiki/Stdint.h)header. See[C syntax#Integral types](https://en.wikipedia.org/wiki/C_syntax#Integral_types)for more information. In addition the types`size_t`

and`ptrdiff_t`

are defined in relation to the address size to hold unsigned and signed integers sufficiently large to handle array indices and the difference between pointers.Perl 5 does not have distinct types. Integers, floating point numbers, strings, etc. are all considered "scalars".[^d](https://en.wikipedia.org#ref_scalars)PHP has two arbitrary-precision libraries. The BCMath library just uses strings as datatype. The GMP library uses an internal "resource" type.[^e](https://en.wikipedia.org#ref_PHP_bignum)The value of[^f](https://en.wikipedia.org#ref_Kinds)`n`

is provided by the`SELECTED_INT_KIND`

intrinsic function.[[4]](https://en.wikipedia.org#cite_note-fortranwiki.org-4)[^g](https://en.wikipedia.org#ref_a68g)[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)G's runtime option`--precision "number"`

can set precision for`long long int`

s to the required "number" significant digits. The*standard*constants`long long int width`

and`long long max int`

can be used to determine actual precision.[^h](https://en.wikipedia.org#ref_Cobol)[COBOL](https://en.wikipedia.org/wiki/COBOL)allows the specification of a required precision and will automatically select an available type capable of representing the specified precision. "`PIC S9999`

", for example, would require a signed variable of four decimal digits precision. If specified as a binary field, this would select a 16-bit signed type on most platforms.[^i](https://en.wikipedia.org#ref_Smalltalk)[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)automatically chooses an appropriate representation for integral numbers. Typically, two representations are present, one for integers fitting the native word size minus any tag bit (SmallInteger) and one supporting arbitrary sized integers (LargeInteger). Arithmetic operations support polymorphic arguments and return the result in the most appropriate compact representation.[^j](https://en.wikipedia.org#ref_Ada_range)[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))range types are checked for boundary violations at run-time (as well as at compile-time for static expressions). Run-time boundary violations raise a "constraint error" exception. Ranges are not restricted to powers of two. Commonly predefined Integer subtypes are: Positive (`range 1 .. Integer'Last`

) and Natural (`range 0 .. Integer'Last`

).`Short_Short_Integer`

(8 bits),`Short_Integer`

(16 bits) and`Long_Integer`

(64 bits) are also commonly predefined, but not required by the Ada standard. Runtime checks can be disabled if performance is more important than integrity checks.[^k](https://en.wikipedia.org#ref_Ada_mod)[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))modulo types implement modulo arithmetic in all operations, i.e. no range violations are possible. Modulos are not restricted to powers of two.Commonly used for characters like Java's char.[^l](https://en.wikipedia.org#ref_Scala_char)[^m](https://en.wikipedia.org#ref_PHP_32/64_bit_long)`int`

in PHP has the same width as`long`

type in C has on that system.[[c]](https://en.wikipedia.org#endnote_CInt)[^n](https://en.wikipedia.org#ref_Erlang_int)[Erlang](https://en.wikipedia.org/wiki/Erlang_(programming_language))is dynamically typed. The type identifiers are usually used to specify types of record fields and the argument and return types of functions.[[5]](https://en.wikipedia.org#cite_note-5)When it exceeds one word.[^o](https://en.wikipedia.org#ref_Erlang_arb)[[6]](https://en.wikipedia.org#cite_note-6)

|
|---|

[Double precision](https://en.wikipedia.org/wiki/Double_precision)

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`Float`

`Long_Float`

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`real`

[[a]](https://en.wikipedia.org#endnote_a68)`long real`

[[a]](https://en.wikipedia.org#endnote_a68)`short real`

, `long long real`

, etc.[[d]](https://en.wikipedia.org#endnote_a68g)[C](https://en.wikipedia.org/wiki/C_(programming_language))`float`

[[b]](https://en.wikipedia.org#endnote_lax_floats)`double`

`long double`

[[f]](https://en.wikipedia.org#endnote_C-long-double)[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)[Objective-C](https://en.wikipedia.org/wiki/Objective-C)([Cocoa](https://en.wikipedia.org/wiki/Cocoa_(API)))`CGFloat`

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`float`

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`float32`

`float64`

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`f32`

`f64`

`f16, f128`

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`Float`

or `Float32`

`Double`

or `Float64`

`Float80`

[[g]](https://en.wikipedia.org#endnote_Swift-long-double)`CGFloat`

[D](https://en.wikipedia.org/wiki/D_(programming_language))`float`

`double`

`real`

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`single-float`

`double-float`

`float, short-float, long-float`

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))([FPC](https://en.wikipedia.org/wiki/Free_Pascal))`single`

`double`

`real`

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Single`

`Double`

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)[Xojo](https://en.wikipedia.org/wiki/Xojo)[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`float`

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`Number`

[[7]](https://en.wikipedia.org#cite_note-Javascript_numbers-7)[S-Lang](https://en.wikipedia.org/wiki/S-Lang)[Fortran](https://en.wikipedia.org/wiki/Fortran)`REAL(KIND = n)`

[[c]](https://en.wikipedia.org#endnote_real_inds)[PHP](https://en.wikipedia.org/wiki/PHP)`float`

[Perl](https://en.wikipedia.org/wiki/Perl)[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`num32`

`num64`

`Num`

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`Float`

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`Float`

`Double`

[Seed7](https://en.wikipedia.org/wiki/Seed7)`float`

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)`Float`

`Double`

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)[OCaml](https://en.wikipedia.org/wiki/OCaml)`float`

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`float32`

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`real`

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`Float`

`Double`

[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))`REAL_32`

`REAL_64`

[COBOL](https://en.wikipedia.org/wiki/COBOL)`FLOAT-BINARY-7`

[[e]](https://en.wikipedia.org#endnote_Cobol_ieee)`FLOAT-BINARY-34`

[[e]](https://en.wikipedia.org#endnote_Cobol_ieee)`FLOAT-SHORT`

, `FLOAT-LONG`

, `FLOAT-EXTENDED`

[Mathematica](https://en.wikipedia.org/wiki/Mathematica)`Real`

The[^a](https://en.wikipedia.org#ref_a68_real)*standard*constants`real shorts`

and`real lengths`

can be used to determine how many`short`

s and`long`

s can be usefully prefixed to`short real`

and`long real`

. The actual sizes of`short real`

,`real`

, and`long real`

are available as the constants`short max real`

,`max real`

and`long max real`

etc. With the constants`short small real`

,`small real`

and`long small real`

available for each type's[machine epsilon](https://en.wikipedia.org/wiki/Machine_epsilon).declarations of single precision often are not honored[^b](https://en.wikipedia.org#ref_lax_floats)The value of[^c](https://en.wikipedia.org#ref_real_kinds)`n`

is provided by the`SELECTED_REAL_KIND`

intrinsic function.[[8]](https://en.wikipedia.org#cite_note-ReferenceA-8)[^d](https://en.wikipedia.org#ref_a68g-real)[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)G's runtime option`--precision "number"`

can set precision for`long long real`

s to the required "number" significant digits. The*standard*constants`long long real width`

and`long long max real`

can be used to determine actual precision.These[^e](https://en.wikipedia.org#ref_Cobol-ieee)[IEEE](https://en.wikipedia.org/wiki/IEEE)floating-point types will be introduced in the next COBOL standard.Same size as[^f](https://en.wikipedia.org#ref_C-long-double)`double`

on many implementations.Swift supports 80-bit[^g](https://en.wikipedia.org#ref_Swift-long-double)[extended precision](https://en.wikipedia.org/wiki/Extended_precision#Language_support)floating point type, equivalent to`long double`

in C languages.

| Integer | Single precision | Double precision | Half and Quadruple precision etc. | |
|---|---|---|---|---|
|

`Complex`

[[b]](https://en.wikipedia.org#endnote_generic_type)`Complex`

[[b]](https://en.wikipedia.org#endnote_generic_type)`Complex`

[[b]](https://en.wikipedia.org#endnote_generic_type)[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`compl`

`long compl`

etc.
`short compl`

etc. and `long long compl`

etc.
[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))[[9]](https://en.wikipedia.org#cite_note-9)`float complex`

`double complex`

[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)`std::complex<float>`

`std::complex<double>`

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`System.Numerics.Complex`

(.NET 4.0)

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`complex64`

`complex128`

[D](https://en.wikipedia.org/wiki/D_(programming_language))`cfloat`

`cdouble`

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`System.Numerics.Complex`

(.NET 4.0)

[Perl](https://en.wikipedia.org/wiki/Perl)`Math::Complex`

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`complex64`

`complex128`

`Complex`

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`complex`

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[S-Lang](https://en.wikipedia.org/wiki/S-Lang)[Fortran](https://en.wikipedia.org/wiki/Fortran)`COMPLEX(KIND = n)`

[[a]](https://en.wikipedia.org#endnote_complex_kinds)[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`Complex`

`Complex`

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))[Seed7](https://en.wikipedia.org/wiki/Seed7)`complex`

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)`Complex`

`Complex`

`Complex`

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)[OCaml](https://en.wikipedia.org/wiki/OCaml)`Complex.t`

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`System.Numerics.Complex`

(.NET 4.0)

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`Complex.Complex Float`

`Complex.Complex Double`

[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))[COBOL](https://en.wikipedia.org/wiki/COBOL)[Mathematica](https://en.wikipedia.org/wiki/Mathematica)`Complex`

`Complex`

The value of[^a](https://en.wikipedia.org#ref_complex_kinds)`n`

is provided by the`SELECTED_REAL_KIND`

intrinsic function.[[8]](https://en.wikipedia.org#cite_note-ReferenceA-8)Generic type which can be instantiated with any base floating point type.[^b](https://en.wikipedia.org#ref_generic_type)

### Other variable types

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=6)]

| Text |
|
|---|

[Enumeration](https://en.wikipedia.org/wiki/Enumerated_type)

[Object](https://en.wikipedia.org/wiki/Object_(computer_science))/

[Universal](https://en.wikipedia.org/wiki/Top_type)

[Character](https://en.wikipedia.org/wiki/Character_(computing))

[String](https://en.wikipedia.org/wiki/String_(computer_science))


[[a]](https://en.wikipedia.org#endnote_string)[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`Character`

`String`

, `Bounded_String`

, `Unbounded_String`

`Boolean`

`(`*item*1, *item*2, *...*)

`tagged null record`

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`char`

`string`

, `bytes`

`bool`

, `bits`

[User defined](http://rosettacode.org/wiki/Enumerations#ALGOL_68)[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`char`

, `wchar_t`

`bool`

[[b]](https://en.wikipedia.org#endnote_int_bool)`enum `*«name»* { *item*1, *item*2, *...* };

[void](https://en.wikipedia.org/wiki/Void_type) [*](https://en.wikipedia.org/wiki/Pointer_(computer_programming))

[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)`«std::»string`

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`unichar`

`NSString *`

`BOOL`

`id`

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`char`

`string`

`bool`

`enum `*name* { *item*1« = *value*», *item*2« = *value*», *...* }

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`String`

`boolean`

`enum `*name* { *item*1, *item*2, *...* }

`Object`

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`byte`

, `rune`

`string`

`bool`

`const (`

*item*1 = *iota*

*item*2

*...*

)

`interface{}`

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`char`

`String`

`bool`

`enum `*name* { *item*1« = *value*», *item*2« = *value*», *...* }

`std::any::Any`

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`Character`

`String`

`Bool`

`enum `*name* { case *item*1, *item*2, *...* }

`Any`

[D](https://en.wikipedia.org/wiki/D_(programming_language))`char`

`string`

`bool`

`enum `*name* { *item*1, *item*2, *...* }

`std.variant.Variant`

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`character`

`string`

`boolean`

`(member `*item*1 *item*2 *...*)

`t`

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`char`

`boolean`

`( `*item*1, *item*2, *...* )

[Object Pascal](https://en.wikipedia.org/wiki/Object_Pascal)([Delphi](https://en.wikipedia.org/wiki/Delphi_(software)))`string`

`variant`

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`String`

`Boolean`

`Enum `*name*

*item*1 «= *value*»

*item*2 «= *value»*

...

End Enum

`Variant`

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Char`

`Object`

[Xojo](https://en.wikipedia.org/wiki/Xojo)`Object`

or `Variant`

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))[[d]](https://en.wikipedia.org#endnote_string_as_char)`str`

`bool`

`from enum import Enum`

`class Name(Enum):`

item=1valueitem=2value...

`object`

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[[d]](https://en.wikipedia.org#endnote_string_as_char)`String`

`Boolean`

`Object`

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)[Fortran](https://en.wikipedia.org/wiki/Fortran)`CHARACTER(LEN = *)`

`CHARACTER(LEN = :), allocatable`

`LOGICAL(KIND = n)`

[[f]](https://en.wikipedia.org#endnote_logical_kinds)`CLASS(*)`

[PHP](https://en.wikipedia.org/wiki/PHP)[[d]](https://en.wikipedia.org#endnote_string_as_char)`string`

`bool`

[Perl](https://en.wikipedia.org/wiki/Perl)[[d]](https://en.wikipedia.org#endnote_string_as_char)`UNIVERSAL`

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`Char`

`Str`

`Bool`

`enum `*name<item*1 item2 ...>

`enum `*name «:item*1(value) :item2(value) ..»

`Mu`

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))[[d]](https://en.wikipedia.org#endnote_string_as_char)`String`

`Object`

[[c]](https://en.wikipedia.org#endnote_Ruby's_bool)`Object`

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`Char`

`String`

`Boolean`

`object `*name* extends Enumeration {

*val item*1, item2, ... = Value

}

`Any`

[Seed7](https://en.wikipedia.org/wiki/Seed7)`char`

`string`

`boolean`

`const type`*: name* is new enum

*item*1,

*item*2,

*...*

end enum;

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)[OCaml](https://en.wikipedia.org/wiki/OCaml)`char`

`string`

`bool`

[[e]](https://en.wikipedia.org#endnote_enum)[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`type `*name* = *item*1 = *value* |*item*2 = *value* | *...*

`obj`

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)[[e]](https://en.wikipedia.org#endnote_enum)[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`Char`

`String`

`Bool`

[[e]](https://en.wikipedia.org#endnote_enum)[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))`CHARACTER`

`STRING`

`BOOLEAN`

`ANY`

[COBOL](https://en.wikipedia.org/wiki/COBOL)`PIC X`

`PIC X(`*string length*)

or `PIC X«X...»`

`PIC 1«(`*number of digits*)»

or `PIC 1«1...»`

`OBJECT REFERENCE`

[Mathematica](https://en.wikipedia.org/wiki/Mathematica)[[d]](https://en.wikipedia.org#endnote_string_as_char)`String`

specifically, strings of arbitrary length and automatically managed.[^a](https://en.wikipedia.org#ref_string)This language represents a boolean as an integer where false is represented as a value of zero and true by a non-zero value.[^b](https://en.wikipedia.org#ref_int_bool)All values evaluate to either true or false. Everything in[^c](https://en.wikipedia.org#ref_Ruby's_bool)evaluates to true and everything in`TrueClass`

evaluates to false.`FalseClass`

This language does not have a separate character type. Characters are represented as strings of length 1.[^d](https://en.wikipedia.org#ref_string_as_char)Enumerations in this language are algebraic types with only nullary constructors[^e](https://en.wikipedia.org#ref_enum)The value of[^f](https://en.wikipedia.org#ref_logical_kinds)is provided by the`n`

`SELECTED_INT_KIND`

intrinsic function.[[4]](https://en.wikipedia.org#cite_note-fortranwiki.org-4)

## Derived types

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=7)]

| fixed size array | dynamic size array | |||
|---|---|---|---|---|
|

[multidimensional array](https://en.wikipedia.org/wiki/Array_data_structure#Multidimensional_arrays)

[one-dimensional array](https://en.wikipedia.org/wiki/Array_data_structure#One-dimensional_arrays)

[multidimensional array](https://en.wikipedia.org/wiki/Array_data_structure#Multidimensional_arrays)

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`array (`*<first> *..* <last>*) of* <type>*

or

`array (`*<discrete_type>*) of* <type>*

`array (`*<first*1> ..* <last*1>,* <first*2> ..* <last*2>, *...*) of* <type>*

or

`array (`*<discrete_type*1>,* <discrete_type*2>,* ...*) of* <type>*

`array (`*<discrete_type> *range <>) of* <type>*

`array (`*<discrete_type*1> range <>,* <discrete_type*2> range <>, *...*) of* <type>*

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`[`*first*:*last*]«modename»

or simply:

`[`*size*]«modename»

`[`*first*1:*last*1,* first*2:*last*2]«modename»

or

`[`*first*1:*last*1][*first*2:*last*2]«modename»

etc.

`flex[`*first*:*last*]«modename»

or simply:

`flex[`*size*]«modename»

`flex[`*first*1:*last*1,* first*2:*last*2]«modename»

or

`flex[`*first*1:*last*1]flex[*first*2:*last*2]«modename» *etc.*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))*type name*[*size*]

[[a]](https://en.wikipedia.org#endnote_C's_array)*type name*[*size*1][*size*2]

[[a]](https://en.wikipedia.org#endnote_C's_array)*type* **name*

or within a block:

*int n = ...; type name*[*n*]

[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)[«std::»array](https://en.wikipedia.org/wiki/Std::array)<*type, size*>

(C++11)
[«std::»vector](https://en.wikipedia.org/wiki/Std::vector)<*type*>

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))*type*[]

*type*[,,*...*]

`System`.Collections.ArrayList

or

`System`.Collections.Generic.List<*type*>

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))*type*[]

[[b]](https://en.wikipedia.org#endnote_Java's_array)*type*[][]*...*

[[b]](https://en.wikipedia.org#endnote_Java's_array)`ArrayList `*or* ArrayList<*type*>

[D](https://en.wikipedia.org/wiki/D_(programming_language))*type*[*size*]

*type*[*size*1][*size*2]

*type*[]

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`[`*size*]*type*

`[`*size*1][*size*2]*...type*

`[]type`

`[][]type`

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`[`*type; size*]

`[[`*type; size*1]*; size*2]

`Vec<`*type*>

`Vec<Vec<`*type*>>

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`[`*type*]

or `Array<`*type*>

`[[`*type*]]

or `Array<Array<`*type*>>

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`NSArray`

`NSMutableArray`

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`Array`

[[d]](https://en.wikipedia.org#endnote_JavaScript's_array)[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(simple-array type (dimension))`

`(simple-array type (dimension1 dimension2))`

`(array type (dimension))`

`(array type (dimension1 dimension2))`

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`array[`*first*..*last*] of *type*

[[c]](https://en.wikipedia.org#endnote_subrange)`array[`*first*1..*last*1] of array[*first*2..*last*2]* ...* of *type*

[[c]](https://en.wikipedia.org#endnote_subrange)or

` array[`*first*1..*last*1,* first*2..*last*2,* ...*] of *type*

[[c]](https://en.wikipedia.org#endnote_subrange)[Object Pascal](https://en.wikipedia.org/wiki/Object_Pascal)([Delphi](https://en.wikipedia.org/wiki/Delphi_(software)))`array of`* type*

`array of array `*...* of *type*

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Dim x(`*last*) As *type*

`Dim x(`*last*1, *last*2,*...*) As *type*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)*type*()

*type*(,,*...*)

`System`.Collections.ArrayList

or

`System`.Collections.Generic.List(Of *type*)

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`list`

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`x = `*type*[*size*];

`x = `*type*[*size*1,* size*2, *...*];

[Fortran](https://en.wikipedia.org/wiki/Fortran)*type* :: *name*(*size*)

*type* :: *name*(*size*1, *size*2,...)

*type*, ALLOCATABLE :: *name*(:)

*type*, ALLOCATABLE :: *name*(:,:,...)

[PHP](https://en.wikipedia.org/wiki/PHP)`array`

[Perl](https://en.wikipedia.org/wiki/Perl)[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`Array[`*type*] *or* Array of *type*

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`x = Array.new(`*size*1){ Array.new(*size*2) }

`Array`

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`Array[`*type*]

`Array[`*...*[Array[*type*]]*...*]

`ArrayBuffer[`*type*]

[Seed7](https://en.wikipedia.org/wiki/Seed7)`array `*type*

or

`array [`*idxType*] *type*

`array array `*type*

or

`array [`*idxType*] array [*idxType*] *type*

`array `*type*

or

`array [`*idxType*] *type*

`array array `*type*

or

`array [`*idxType*] array [*idxType*] *type*

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)`Array`

`OrderedCollection`

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)*type*[]

*type*[,,*...*]

[OCaml](https://en.wikipedia.org/wiki/OCaml)*type* array

*type* array *...* array

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))*type* []

or

*type* array

*type* [,,*...*]

`System`.Collections.ArrayList

or

`System`.Collections.Generic.List<*type*>

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)*type* vector *or type* array

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`x = Array.array (0,`

*size*-1) *list_of_association_pairs*

`x = Array.array ((0, 0,`

*...*), (*size*1-1, *size*2-1,*...*)) *list_of_association_pairs*

[COBOL](https://en.wikipedia.org/wiki/COBOL)*level-number type* OCCURS *size* «TIMES».

*one-dimensional array definition...**level-number type* OCCURS *min-size* TO *max-size* `«TIMES» DEPENDING «ON»`

*size*.

[[e]](https://en.wikipedia.org#endnote_COBOL_DEPENDING_ON_clause)In most expressions (except the[^a](https://en.wikipedia.org#ref_C's_array)

and[sizeof](https://en.wikipedia.org/wiki/Sizeof)`&`

operators), values of array types in C are automatically converted to a pointer of its first argument. See[C syntax#Arrays](https://en.wikipedia.org/wiki/C_syntax#Arrays)for further details of syntax and pointer operations.The C-like[^b](https://en.wikipedia.org#ref_Java's_array)

works in Java, however*type*x[]

is the preferred form of array declaration.*type*[] xSubranges are used to define the bounds of the array.[^c](https://en.wikipedia.org#ref_subrange)JavaScript's array are a special kind of object.[^d](https://en.wikipedia.org#ref_JavaScript's_array)The[^e](https://en.wikipedia.org#ref_COBOL_DEPENDING_ON_clause)`DEPENDING ON`

clause in COBOL does not create a*true*variable length array and will always allocate the maximum size of the array.

### Other types

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=9)]

| Simple composite types |
|
|---|

[Unions](https://en.wikipedia.org/wiki/Union_(computer_science))

[Records](https://en.wikipedia.org/wiki/Record_(computer_science))

[Tuple](https://en.wikipedia.org/wiki/Tuple)expression

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`type `*name* is «abstract» «tagged» «limited» *[*record

*field*1 : *type*;

*field*2 : *type*;

*...*

end record *|* null record*]*

`type `*name* (*variation* : *discrete_type*) is record

case *variation* is

when *choice_list*1 =>

*fieldname*1 : *type*;

*...*

when *choice_list*2 =>

*fieldname*2 : *type*;

*...*

*...*

end case;

end record

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`struct `*(*modename *«fieldname»,* ...*);*

[user-defined](https://en.wikipedia.org/wiki/User-defined_function)`union `*(*modename*,* ...*);*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`struct `*«name»* {*type name*;*...*};

`union {`*type name*;*...*};

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)`struct `*«name»* {*type name*;*...*};

[[b]](https://en.wikipedia.org#endnote_C++'s_struct)[«std::»tuple](https://en.wikipedia.org/wiki/C%2B%2B11#Tuple_types)<*type*1..typen>

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`struct `*name* {*type name*;*...*}

`(`*val*1, *val*2, *...* )

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))[[a]](https://en.wikipedia.org#endnote_just_classes)[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[D](https://en.wikipedia.org/wiki/D_(programming_language))`struct `*name* {*type name*;*...*}

`std.variant.Algebraic`*!(type,...)*

`union {`*type name*;*...*}

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`struct { `

*«name» type*

*...*

}

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`struct name {`*name:* type*, ...*}

`(`*val*1,* val*2, *...* )

`enum name { `*Foo*(*types*)*, ...*}

`union name {`*name:* type*, ...*}

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`struct `*name* {

var* name «*:* type»*

...

}

`(`*«name*1:*» val*1, *«name*2:*» val*2, *«name*3:*» val*3, *...* )

`enum `*name* { case *Foo«*(*types*)» case *Bar* «(*types*)» *...* }

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(defstruct name slot-name (slot-name initial-value) (slot-name initial-value :type type) ...)`

`(cons `*val*1 val2)

[[c]](https://en.wikipedia.org#endnote_pair_only)[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`record`

*name*: *type*;

*...*

end

`record`

case *type* of

*value*: (*types*);

*...*

end

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Structure `*name*

Dim *name* As *type*

*...*

End Structure

`(`*val*1, *val*2, *...* )

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))[[a]](https://en.wikipedia.org#endnote_just_classes)`«(`*»val*1, *val*2, *val*3, *...* «)»

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`struct {`*name [=value], ...*}

[Fortran](https://en.wikipedia.org/wiki/Fortran)`TYPE `*name*

type :: *name*

...

END TYPE

[PHP](https://en.wikipedia.org/wiki/PHP)[[a]](https://en.wikipedia.org#endnote_just_classes)[Perl](https://en.wikipedia.org/wiki/Perl)[[d]](https://en.wikipedia.org#endnote_Perl's_records)[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))[[a]](https://en.wikipedia.org#endnote_just_classes)[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`OpenStruct.new({:name => value})`

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`case class `*name*(«*var*» *name*: *type*, *...*)

`(`*val*1, *val*2, *val*3, *...* )

`abstract class `*name*

case class *Foo*(«*parameters*») extends *name*

case class *Bar*(«*parameters*») extends *name*

*...*

or

`abstract class `*name*

case object *Foo* extends *name*

case object *Bar* extends *name*

*...*

or a combination of case classes and case objects

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)[OCaml](https://en.wikipedia.org/wiki/OCaml)`type `*name* = {«*mutable*» *name* : *type*;*...*}

`«(»`*val*1, *val*2, *val*3, *...* «)»

`type `*name* = *Foo* «of *type*» | *Bar* «of *type*» | *...*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`type `*name* = {*name* : *type*,*...*}

`(`*val*1, *val*2, *val*3, *...* )

`datatype `*name* = *Foo* «of *type*» | *Bar* «of *type*» | *...*

[Haskell](https://en.wikipedia.org/wiki/Haskell)`data `*Name* = *Constr* {*name* :: *type*,*...*}

`data `*Name* = *Foo* «*types*» | *Bar* «*types*» | *...*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`level-number name type clauses`

.

`level-number+n name type clauses`

.

*...*

*name* REDEFINES *variable type*.

Only classes are supported.[^a](https://en.wikipedia.org#ref_just_classes)[^b](https://en.wikipedia.org#ref_C++'s_struct)`struct`

s in C++ are actually classes, but have default public visibility and*are*also[POD](https://en.wikipedia.org/wiki/Plain_old_data_structure)objects. C++11 extended this further, to make classes act identically to POD objects in many more cases.pair only[^c](https://en.wikipedia.org#ref_pair_only)Although Perl doesn't have records, because Perl's type system allows different data types to be in an array, "hashes" (associative arrays) that don't have a variable index would effectively be the same as records.[^d](https://en.wikipedia.org#ref_Perl's_records)Enumerations in this language are algebraic types with only nullary constructors[^e](https://en.wikipedia.org#ref_enum)

## Variable and constant declarations

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=10)]

| variable | constant | type synonym | |
|---|---|---|---|
|

*identifier* : *type«* := *initial_value»*

[[e]](https://en.wikipedia.org#endnote_Ada_declaration)*identifier* : constant *type* := *final_value*

`subtype `*identifier* is *type*

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`modename name« := `*initial_value*»;

`modename name = `*value*;

[mode](https://en.wikipedia.org/wiki/Typedef) synonym = modename;

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))*type name*« = *initial_value*»;

`enum{ `*name* = *value* };

[typedef](https://en.wikipedia.org/wiki/Typedef) *type synonym*;

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)`const `*type name* = *value*;

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))*type name*1« = *initial_value*», *name*2« = *initial_value*», *...*;

or

`var `*name* = *initial_value*;

`const `*type name* = *value*, *name* = *value*, *...*;

or

`readonly `*type name* = *value*, *name* = *value*, *...* ;

`using `*synonym* = *type*;

[D](https://en.wikipedia.org/wiki/D_(programming_language))*type name*« = *initial_value*»;

or

`auto `*name* = *value*;

`const `*type name* = *value*;

or

`immutable `*type name* = *value*;

`alias `*type synonym*;

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))*type name*« = *initial_value*»;

`final `*type name* = *value*;

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`var `*name*« = *initial_value*»;

or`let `*name*« = *initial_value*»;

(since [ECMAScript](https://en.wikipedia.org/wiki/ECMAScript)2015)`const `*name* = *value*;

(since [ECMAScript](https://en.wikipedia.org/wiki/ECMAScript)2015)[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`var `*name type*« = *initial_value*»

or

*name* := *initial_value*

`const `*name «type»* = *value*

`type `*synonym type*

[Racket](https://en.wikipedia.org/wiki/Racket_(programming_language))`(define `*name expression*)

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))[[f]](https://en.wikipedia.org#endnote_Rust_declaration)`let mut `*name*«: *type*»« = *initial_value*»;

`static mut `*NAME*: *type* = *value*;

`let `*name*«: *type*»« = *initial_value*»;

`const `*NAME*: *type* = *value*;

`static `*NAME*: *type* = *value*;

`type `*synonym* = *typename*;

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`var `*name* «: *type*»« = *initial_value*»

`let `*name* «: *type*» = *value*

`typealias `*synonym* = *type*

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(defparameter `*name initial-value*)

or

`(defvar `*name initial-value*)

`(defconstant `*name value*)

`(deftype `*synonym* () '*type*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(define `*name initial_value*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(defglobal `*name initial_value*)

or

`(defdynamic `*name initial_value*)

`(defconstant `*name value*)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))[[a]](https://en.wikipedia.org#endnote_Pascal's_declarations)*name*: *type*« = *initial_value*»

*name* = *value*

*synonym* = *type*

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Dim `*name* «As *type*»

Constants use the same syntax, and:

- use
`Const`

instead of`Dim`

- have a restriction to only certain primitive types
`Const`

*name*«As1*type*» =*value*,*name*«As2*type»*=*value, ...*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)[[10]](https://en.wikipedia.org#cite_note-10)Given that there exist the identifier suffixes ("modifiers"):

`type_character`

, available as an alternative to an`As`

clause for some primitive data types;`nullable_specifier`

; and`array_specifier`

;

and that

- a
`modified_identifier`

is of the form`identifier«type_character»«nullable_specifier»«array_specifier»`

; - a
`modified_identifier_list`

is a comma-separated list of two or more occurrences of`modified_identifier`

; and - a
`declarator_list`

is a comma-separated list of declarators, which can be of the form*identifier*As*object_creation_expression**(object initializer declarator)*,*modified_identifier*«As*non_array_type*«*array_rank_specifier*»»« =*initial_value»**(single declarator)*, or*modified_identifier_list*«As*«non_array_type*««*array_rank_specifier*»»*(multiple declarator);*


valid declaration statements are of the form
`Dim `

,
where, for the purpose of semantic analysis, to convert the *declarator_list*`declarator_list`

to a list of only single declarators:

- The
`As`

clauses of each*multiple declarator*is distributed over its`modified_identifier_list`

- The
`As New`

of each*type...**object initializer declarator*is replaced with`As`

*type*= New*type...*

and for which, for each `identifier`

,

- a
`type_character`

and`As`

clause do not both appear; - if an
`As`

clause is present,- an
`array_rank_specifier`

does not appear both as a modification of the identifier and on the type of the`As`

clause;

- an
- an
`unmodified_type`

can be determined, by the rule that,- if a
`type_character`

or`As`

clause is present,`unmodified_type`

is that specified by such construct,

- and that otherwise,
- either
`Option Infer`

must be on and the`identifier`

must have an initializer, in which case`unmodified_type`

is that of the initializer, or `Option Strict`

must be off, in which case`unmodified_type`

is`Object`

;

- either

- if a
- its
`final_type`

is its`unmodified_type`

prepended before its modifiers; - its
`final_type`

is a valid type; and - if an
`initial_value`

is present,- either
`Option Strict`

is on and`initial_value`

has a widening conversion to`final_type`

, or `Option Strict`

is off and`initial_value`

has a narrowing conversion to`final_type`

.

- either

If `Option Explicit`

is off, variables do not require explicit declaration; they are declared implicitly when used:
`name = initial_value`


`Imports `*synonym* = *type*

[Xojo](https://en.wikipedia.org/wiki/Xojo)`Dim `*name* «As *type*»« = *initial_value»*

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))*name«: type»* = *initial_value*

*synonym* = *type*

[[b]](https://en.wikipedia.org#endnote_variable_types)[CoffeeScript](https://en.wikipedia.org/wiki/CoffeeScript)*name* = *initial_value*

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)*name* = *initial_value*;

`typedef struct {...} `*typename*

[Fortran](https://en.wikipedia.org/wiki/Fortran)*type* :: *name*

*type*, PARAMETER :: *name* = *value*

[PHP](https://en.wikipedia.org/wiki/PHP)`$`*name* = *initial_value*;

`define("`*name*", *value*);

const *name* = *value (5.3+)*

[Perl](https://en.wikipedia.org/wiki/Perl)`«my» $`*name*« = *initial_value*»;

[[c]](https://en.wikipedia.org#endnote_Perl's_my_keyword)`use constant `*name* => *value*;

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`«my «`*type*»» *$name«* = *initial_value*»;

[[c]](https://en.wikipedia.org#endnote_Perl's_my_keyword)`«my «`*type*»» constant *name* = *value*;

`::`*synonym* ::= *type*

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))*name* = *initial_value*

*Name* = *value*

*synonym* = *type*

[[b]](https://en.wikipedia.org#endnote_variable_types)[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`var `*name*«: *type*» = *initial_value*

`val `*name*«: *type*» = *value*

`type `*synonym* = *type*

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`«[`*type*]» $*name* = *initial_value*

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`name=`*initial_value*

[OCaml](https://en.wikipedia.org/wiki/OCaml)`let `*name*« : *type* ref» = ref *value*

[[d]](https://en.wikipedia.org#endnote_ML_ref)`let `*name* «: *type*» = *value*

`type `*synonym* = *type*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`let mutable `*name* «: *type*» = *value*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`val `*name* «: *type* ref» = ref *value*

[[d]](https://en.wikipedia.org#endnote_ML_ref)`val `*name* «: *type*» = *value*

[Haskell](https://en.wikipedia.org/wiki/Haskell)`«`*name*::*type*;» *name* = *value*

`type `*Synonym* = *type*

[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))`VARIABLE `*name*

(in some systems use *value* VARIABLE *name*

instead)
*value* CONSTANT *name*

[COBOL](https://en.wikipedia.org/wiki/COBOL)*level-number name type clauses*.

`«0»1 `*name* CONSTANT «AS» *value*.

*level-number name type clauses* «IS» TYPEDEF.

[Mathematica](https://en.wikipedia.org/wiki/Mathematica)`name=`*initial_value*

Pascal has declaration blocks. See[^a](https://en.wikipedia.org#ref_Pascal's_declarations)[functions](https://en.wikipedia.org#Functions).Types are just regular objects, so you can just assign them.[^b](https://en.wikipedia.org#ref_variable_types)In Perl, the "my" keyword scopes the variable into the block.[^c](https://en.wikipedia.org#ref_Perl's_my_keyword)Technically, this does not declare[^d](https://en.wikipedia.org#ref_ML_ref)*name*to be a mutable variable—in ML, all names can only be bound once; rather, it declares*name*to point to a "reference" data structure, which is a simple mutable cell. The data structure can then be read and written to using the`!`

and`:=`

operators, respectively.If no initial value is given, an invalid value is automatically assigned (which will trigger a run-time exception if it used before a valid value has been assigned). While this behaviour can be suppressed it is recommended in the interest of predictability. If no invalid value can be found for a type (for example in case of an unconstraint integer type), a valid, yet predictable value is chosen instead.[^e](https://en.wikipedia.org#ref_Ada_declaration)In Rust, if no initial value is given to a[^f](https://en.wikipedia.org#ref_Rust_declaration)`let`

or`let mut`

variable and it is never assigned to later, there is an["unused variable" warning](https://doc.rust-lang.org/rustc/lints/listing/warn-by-default.html#unused-variables). If no value is provided for a`const`

or`static`

or`static mut`

variable, there is an error. There is a["non-upper-case globals"](https://doc.rust-lang.org/rustc/lints/listing/warn-by-default.html?#non-upper-case-globals)error for non-uppercase`const`

variables. After it is defined, a`static mut`

variable can only be assigned to in an`unsafe`

block or function.

[Conditional](https://en.wikipedia.org/wiki/Conditional_(programming)) statements

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=12)]

| if | else if |
|
|---|

[conditional expression](https://en.wikipedia.org/wiki/Conditional_(programming)#If_expressions)

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`if `*condition* then

*statements*

«else

*statements*»

end if

`if `*condition*1 then

*statements*

elsif *condition*2 then

*statements*

*...*

«else

*statements*»

end if

`case `*expression* is

when *value_list*1 => *statements*

when *value_list*2 => *statements*

*...*

«when others => *statements*»

end case

`(if `*condition*1 then

*expression*1

«elsif *condition*2 then

*expression*2»

*...*

else

*expression*n

)

or

`(case `*expression* is

when *value_list*1 => *expression*1

when *value_list*2 => *expression*2

*...*

«when others => *expression*n»

)

[Seed7](https://en.wikipedia.org/wiki/Seed7)`if `*condition* then

*statements*

«else

*statements*»

end if

`if `*condition*1 then

*statements*

elsif *condition*2 then

*statements*

*...*

«else

*statements*»

end if

`case `*expression* of

when *set1* : *statements*

*...*

«otherwise: *statements*»

end case

[Modula-2](https://en.wikipedia.org/wiki/Modula-2)`if `*condition* then

*statements*

«else

*statements*»

end

`if `*condition*1 then

*statements*

elsif *condition*2 then

*statements*

*...*

«else

*statements*»

end

`case `*expression* of

*caseLabelList* : *statements* |

*...*

«else *statements*»

end

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`if `*condition* then *statements* «else *statements*» fi

`if `*condition* then *statements* elif *condition* then *statements* fi

`case `*switch* in *statements, statements«,...* out *statements*» esac

`( condition | valueIfTrue | valueIfFalse )`

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)(brief form)

`( condition | statements «| statements» )`

`( condition | statements |: condition | statements )`

`( variable | statements,... «| statements» )`

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))`:If `*condition*

*instructions*

«:Else

*instructions*»

:EndIf

`:If `*condition*

*instructions*

:ElseIf *condition*

*instructions*

*...*

«:Else

*instructions*»

:EndIf

`:Select `*expression*

:Case *case1*

*instructions*

*...*

«:Else

*instructions*»

:EndSelect

`{`*condition*:*valueIfTrue* ⋄ *valueIfFalse*}

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`if (`*condition*) *instructions*

«else *instructions*»

`instructions`

can be a single statement or a block in the form of: `{ `*statements* }

`if (`*condition*) *instructions*

else if (*condition*) *instructions*

*...*

«else *instructions»*

or

`if (`*condition*) *instructions*

else { if (*condition*) *instructions* }

`switch (`*variable*) {

case *case1*: *instructions* «; break;»

*...*

«default: *instructions*»

}

*condition* [?](https://en.wikipedia.org/wiki/%3F:) *valueIfTrue* [:](https://en.wikipedia.org/wiki/%3F:) *valueIfFalse*

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)[D](https://en.wikipedia.org/wiki/D_(programming_language))[Java](https://en.wikipedia.org/wiki/Java_(programming_language))[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[PHP](https://en.wikipedia.org/wiki/PHP)[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`if (`*condition*) *instructions*

«else *instructions*»

`instructions`

can be a single statement or a block in the form of: `{ `

*statements* }

`if (`*condition*) *instructions*

else if (*condition*) *instructions*

*...*

«else *instructions*»

`switch (`*variable*)

{

case *case*1:

*instructions*

«*break_or_jump_statement*»

*...*

«default:

*instructions*

*break_or_jump_statement*»

}

All non-empty cases must end with a `break`

or `goto case`

statement (that is, they are not allowed to fall-through to the next case).
The `default`

case is not required to come last.

*condition* [?](https://en.wikipedia.org/wiki/%3F:) *valueIfTrue* [:](https://en.wikipedia.org/wiki/%3F:) *valueIfFalse*

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`if (`*condition*) *instruction*

«else *instructions*»

`if (`*condition*) { *instructions* }

elseif (*condition*) { *instructions* }

*...*

«else { *instructions* }»

`switch (`*variable*) { *case1*{*instructions* «break;» } *...* «default { *instructions* }»}

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`if `*condition* {*instructions*}

«else {*instructions*}»

`if `*condition* {*instructions*}

else if *condition* {*instructions*}

*...*

«else {*instructions*}»

or

`switch { `

case *condition*: *instructions*

*...*

«default: *instructions*»

}

`switch `*variable* {

case *case*1: *instructions*

*...*

«default: *instructions*»

}

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`if `*condition* {*instructions*}

«else {*instructions*}»

`if `*condition* {*instructions*}

else if *condition* {*instructions*}

*...*

«else {*instructions*}»

`switch `*variable* {

case *case*1: *instructions*

*...*

«default: *instructions*»

}

[Perl](https://en.wikipedia.org/wiki/Perl)`if (`*condition*) {*instructions*}

«else {*instructions*}»

or

`unless (`*notcondition*) {*instructions*}

«else {*instructions*}»

`if (`*condition*) {*instructions*}

elsif (*condition*) {*instructions*}

*...*

«else {*instructions*}»

or

`unless (`*notcondition*) {*instructions*}

elsif (*condition*) {*instructions*}

*...*

«else {*instructions*}»

`use feature "switch";`

*...*

given (*variable*) {

when (*case*1) { *instructions* }

*...*

«default { *instructions* }»

}

*condition* [?](https://en.wikipedia.org/wiki/%3F:) *valueIfTrue* [:](https://en.wikipedia.org/wiki/%3F:) *valueIfFalse*

[Racket](https://en.wikipedia.org/wiki/Racket_(programming_language))`(when `*testexpression expressions*)

or

`(unless `*condition expressions*)

`(cond`

` [`*testexpression expressions*]

` [`*testexpression expressions*]

` `*...*

` [else `*expressions*])

`(case `*expression* [(*case1*) *expressions*]

` [(`*case2*) *expressions*]

` `*...*

` [else `*expressions*])

`(if `*testexpression expressioniftrue expressioniffalse*)

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`if `*condition* {*instructions*}

«else {*instructions*}»

or

`unless `*notcondition* {*instructions*}

`if `*condition* {*instructions*}

elsif *condition* {*instructions*}

...

«else {*instructions*}

`given `*variable* {

when *case*1 { *instructions* }

*...*

«default { *instructions* }»

}

*condition* [??](https://en.wikipedia.org/wiki/%3F:) *valueIfTrue* !! *valueIfFalse*

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`if `*condition*

*instructions*

«else

*instructions»*

`if `*condition*

*instructions*

elsif *condition*

*instructions*

*...*

«else

*instructions*»

end

`case `*variable*

when *case*1

*instructions*

*...*

«else

*instructions*»

end

*condition* [?](https://en.wikipedia.org/wiki/%3F:) *valueIfTrue* [:](https://en.wikipedia.org/wiki/%3F:) *valueIfFalse*

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`if (`*condition*) {*instructions*}

«else {*instructions*}»

`if (`*condition*) {*instructions*}

else if (*condition*) {*instructions*}

...

«else {*instructions*}»

*expression* match {

case *pattern1* => *expression*

case *pattern2* => *expression*

*...*

«case _ => *expression*»

}

[[b]](https://en.wikipedia.org#endnote_pattern_matching)`if (`*condition*) *valueIfTrue* else *valueIfFalse*

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)*condition* ifTrue:

*trueBlock*

«ifFalse:

*falseBlock*»

end

*condition* ifTrue: *trueBlock* ifFalse: *falseBlock*

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)*(when* condition

*instructions*)

or

`(unless `*condition*

*instructions*)

or

`(if `*condition*

(progn *instructions*)

«(progn *instructions*)»)

`(cond (`*condition1 instructions*)

(*condition2 instructions*)

*...*

«(t *instructions*)»)

`(case `*expression*

(*case1 instructions*)

(*case2 instructions*)

*...*

«(otherwise *instructions*)»)

`(if `*test then else*)

or

`(cond (`*test1 value1*) (*test2 value2*) *...*))

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(when `*condition instructions*)

or

`(if `*condition* (begin *instructions*) «(begin *instructions*)»)

`(cond (`*condition1 instructions*) (*condition2 instructions*) *...* «(else *instructions*)»)

`(case (`*variable*) ((*case1*) *instructions*) ((*case2*) *instructions*) *...* «(else *instructions*)»)

`(if `*condition valueIfTrue valueIfFalse*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(if `*condition*

(progn *instructions*)

«(progn *instructions*)»)

`(cond (`*condition1 instructions*)

(*condition2 instructions*)

*...*

«(t *instructions*)»)

`(case `*expression*

(*case1 instructions*)

(*case2 instructions*)

*...*

«(t *instructions*)»)

`(if `*condition valueIfTrue valueIfFalse*)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`if `*condition* then begin

*instructions*

end

«else begin

*instructions*

end»'

[[c]](https://en.wikipedia.org#endnote_pascal_semicolon)`if `*condition* then begin

*instructions*

end

else if *condition* then begin

*instructions*

end

*...*

«else begin

*instructions*

end»

[[c]](https://en.wikipedia.org#endnote_pascal_semicolon)`case `*variable* of

*case1*: *instructions*

*...*

«else: *instructions*»

end

[[c]](https://en.wikipedia.org#endnote_pascal_semicolon)[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`If `*condition* Then

*instructions*

«Else

*instructions*»

End If

Single-line, when

`instructions`

are `instruction`1 : instruction2 : ...

:`If `*condition* Then *instructions* «Else *instructions»*

`If `*condition* Then

*instructions*

ElseIf *condition* Then

*instructions*

*...*

«Else

*instructions*»

End If

Single-line:

See note about C-like languages; the

`Else`

clause of a single-line `If`

statement can contain another single-line `If`

statement.
`Select« Case» `*variable*

Case *case_pattern*1

*instructions*

*...*

«Case Else

*instructions*»

End Select

[IIf](https://en.wikipedia.org/wiki/IIf)(*condition*, *valueIfTrue*, *valueIfFalse*)

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`If(`*condition*, *valueIfTrue*, *valueIfFalse*)

[Xojo](https://en.wikipedia.org/wiki/Xojo)[Python](https://en.wikipedia.org/wiki/Python_(programming_language))[[a]](https://en.wikipedia.org#endnote_python_indent)`if `*condition* :

`Tab ↹`*instructions*

«else:

`Tab ↹`*instructions»*

`if `*condition* :

`Tab ↹`*instructions*

elif *condition* :

`Tab ↹`*instructions*

*...*

«else:

`Tab ↹`*instructions»*

`match `*variable*:

`Tab ↹`case *case1*:

`Tab ↹``Tab ↹`*instructions*

`Tab ↹`case *case2*:

`Tab ↹``Tab ↹`*instructions*

*valueIfTrue* if *condition* else *valueIfFalse*

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`if (`*condition*) { *instructions* } «else { *instructions* }»

`if (`*condition*) { *instructions* } else if (*condition*) { *instructions* } *...* «else { *instructions* }»

`switch (`*variable*) { case *case1*: *instructions* } { case *case2*: *instructions* } *...*

[Fortran](https://en.wikipedia.org/wiki/Fortran)`IF (`*condition*) THEN

*instructions*

ELSE

*instructions*

ENDIF

`IF (`*condition*) THEN

*instructions*

ELSEIF (*condition*) THEN

*instructions*

*...*

ELSE

*instructions*

ENDIF

`SELECT CASE(`*variable*)

CASE (*case1*)

*instructions*

*...*

CASE DEFAULT

*instructions*

END SELECT

[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))*condition* IF *instructions* « ELSE *instructions*» THEN

*condition* IF *instructions* ELSE *condition* IF *instructions* THEN THEN

*value* CASE

*case* OF *instructions* ENDOF

*case* OF *instructions* ENDOF

*default instructions*

ENDCASE

*condition* IF *valueIfTrue *ELSE *valueIfFalse* THEN

[OCaml](https://en.wikipedia.org/wiki/OCaml)`if `*condition* then begin *instructions* end «else begin *instructions* end»

`if `*condition* then begin *instructions* end else if *condition* then begin *instructions* end *...* «else begin *instructions* end»

`match `*value* with

*pattern1* -> *expression*

| *pattern2* -> *expression*

*...*

«| _ -> *expression*»

[[b]](https://en.wikipedia.org#endnote_pattern_matching)`if `*condition* then *valueIfTrue* else *valueIfFalse*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))Either on a single line or with indentation as shown below:
`if `

*condition* then`Tab ↹`*instructions*

«else`Tab ↹`*instructions»*

Verbose syntax mode:

Same as Standard ML.

Either on a single line or with indentation as shown below:

`if `*condition* then

`Tab ↹`*instructions*

elif *condition* then

`Tab ↹`*instructions*

*...*

«else

`Tab ↹`*instructions»*

Verbose syntax mode:

Same as Standard ML.

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`if `*condition* then «(*»instructions «*)»

else «(*» instructions «*)»

`if `*condition* then «(*»instructions «*)»

else if *condition* then «(*» instructions «*)»

*...*

else «(*» instructions «*)»

`case `*value* of

*pattern1* => *expression*

| *pattern2* => *expression*

*...*

«| _ => *expression»*

[[b]](https://en.wikipedia.org#endnote_pattern_matching)[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`if `*condition* then *expression* else *expression*

or

`when `*condition* (do *instructions*)

or

`unless `*notcondition* (do *instructions*)

*result* | *condition* = *expression*

| *condition* = *expression*

| otherwise = *expression*

`case `*value* of {

*pattern1* -> *expression*;

*pattern2* -> *expression*;

*...*

«_ -> *expression»*

}

[[b]](https://en.wikipedia.org#endnote_pattern_matching)[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`if `*condition-command;* then

*expression*

«else

*expression*»

fi

`if `*condition-command;* then

*expression*

elif *condition-command;* then

*expression*

«else

*expression*»

fi

`case `*"$variable"* in

*"$condition1" )*

command...

"$condition2" )

command...

esac

[CoffeeScript](https://en.wikipedia.org/wiki/CoffeeScript)`if `*condition* then *expression* «else *expression»*

or

`if `*condition*

expression

«else

*expression»*

or

*expression* if *condition*

or

`unless `*condition*

*expression*

«else

*expression»*

or

*expression* unless *condition*

`if `*condition* then *expression* else if *condition* then *expression* «else *expression»*

or

`if `*condition*

*expression*

else if *condition*

expression

«else

*expression»*

or

`unless `*condition*

*expression*

else unless *condition*

expression

«else

*expression»*

`switch `*expression*

when *condition* then *expression*

else *expression*

or

`switch `*expression*

when *condition*

*expression*

«else

*expression»*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`IF `*condition* «THEN»

*expression*

«ELSE

*expression»*.

[[d]](https://en.wikipedia.org#endnote_COBOL_END-IF)`EVALUATE `*expression* «ALSO *expression...*»

WHEN *case-or-condition* «ALSO *case-or-condition...»*

expression

...

«WHEN OTHER

*expression*»

END-EVALUATE

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`if `*condition* {

*expression*

}« else {

*expression*

}»

`if `*condition* {

*expression*

} else if *condition* {

expression

}« else {

expression

}*»*

`match `*variable* {

*pattern1* => *expression,*

*pattern2* => *expression,*

*pattern3* => *expression,*

«_ => *expression*»

}

[[b]](https://en.wikipedia.org#endnote_pattern_matching)[[e]](https://en.wikipedia.org#endnote_Rust_match_expression)[select case](https://en.wikipedia.org/wiki/Switch_statement)

[conditional expression](https://en.wikipedia.org/wiki/Conditional_(programming)#If_expressions)

A single instruction can be written on the same line following the colon. Multiple instructions are grouped together in a[^a](https://en.wikipedia.org#ref_python_indent)[block](https://en.wikipedia.org/wiki/Block_(programming))which starts on a newline (The indentation is required). The conditional expression syntax does not follow this rule.This is[^b](https://en.wikipedia.org#ref_pattern_matching)[pattern matching](https://en.wikipedia.org/wiki/Pattern_matching)and is similar to select case but not the same. It is usually used to deconstruct[algebraic data types](https://en.wikipedia.org/wiki/Algebraic_data_type).In languages of the Pascal family, the semicolon is not part of the statement. It is a separator between statements, not a terminator.[^c](https://en.wikipedia.org#ref_pascal_semicolon)[^d](https://en.wikipedia.org#ref_COBOL_END-IF)`END-IF`

may be used instead of the period at the end.In Rust, the comma ([^e](https://en.wikipedia.org#ref_Rust_match_expression)`,`

) at the end of a match arm can be omitted after the last match arm, or after any match arm in which the expression is a block (ends in possibly empty matching brackets`{}`

).

|
|---|

[do while loop](https://en.wikipedia.org/wiki/Do_while_loop)

[(count-controlled) for loop](https://en.wikipedia.org/wiki/For_loop)

[foreach](https://en.wikipedia.org/wiki/Foreach)

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`while `*condition* loop

*statements*

end loop

`loop`

*statements*

exit when not *condition*

end loop

`for `*index* in «reverse» *[first* .. *last | discrete_type]* loop

*statements*

end loop

`for `*item* of «reverse» *iterator* loop

*statements*

end loop

or

`(for [all | some] [in | of] `*[first* .. *last | discrete_type | iterator]* => *predicate*)

[[b]](https://en.wikipedia.org#endnote_Ada_quantifiers)[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`«for `*index*» «from *first*» «by *increment*» «to *last*» «while *condition*» do *statements* od

`for key «to upb list» do «typename val=list[key];» `*statements* od

`«while `*condition*»

do *statements* od

`«while `*statements; condition*»

do *statements* od

`«for `*index*» «from *first*» «by *increment*» «to *last*» do *statements* od

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))`:While `*condition*

*statements*

:EndWhile

`:Repeat`

*statements*

:Until *condition*

`:For `*var«s»* :In *list*

*statements*

:EndFor

`:For `*var«s»* :InEach *list*

*statements*

:EndFor

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`instructions`

can be a single statement or a block in the form of: `{ `*statements* }

`while (`*condition*) *instructions*

`do `*instructions* while (*condition*);

`for (`*«type» i* = *first*; *i* <= *last*; *i*++) *instructions*

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`for (`*type item* in *set*) *instructions*

[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)`«std::»for_each(`*start*, *end*, *function*)

Since

[C++11](https://en.wikipedia.org/wiki/C%2B%2B11):`for (`*type item* : *set*) *instructions*

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`foreach (`*type item* in *set*) *instructions*

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`for (`*type item* : *set*) *instructions*

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`for (var `*i* = *first*; *i* <= *last*; *i*++) *instructions*

[EcmaScript](https://en.wikipedia.org/wiki/EcmaScript)2015:[[11]](https://en.wikipedia.org#cite_note-11)`for (var `

*item* of *set*) *instructions*

[PHP](https://en.wikipedia.org/wiki/PHP)`foreach (range(`*first*, *last*) as $i) *instructions*

or

`for ($i = `*first*; $i <= *last*; $i++) *instructions*

`foreach (`*set* as *item*) *instructions*

or

`foreach (`*set* as *key* => *item*) *instructions*

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`for ($i = `*first*; $i -le *last*; $i++) *instructions*

`foreach (`*item* in *set*) *instructions*

[D](https://en.wikipedia.org/wiki/D_(programming_language))`foreach `*(i;* first *...* last) *instructions*

`foreach `*(«type» item; set) instructions*

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`for `*condition* { *instructions* }

`for `*i* := *first*; *i* <= *last*; *i*++ { *instructions* }

`for `*key*, *item* := range *set* { *instructions* }

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`while `*condition* { *instructions* }

`repeat { `*instructions* } while *condition*

1.x:

`do { `*instructions* } while *condition*

`for `*i* = *first* ... *last* { *instructions* }

or

`for `*i* = *first* ..< *last*+1 { *instructions* }

or

`for var `*i* = *first*; *i* <= *last*; *i*++ { *instructions* }

`for `*item* in *set* { *instructions* }

[Perl](https://en.wikipedia.org/wiki/Perl)`while (`*condition*) { *instructions* }

or

`until (`*notcondition*) { *instructions* }

`do { `*instructions* } while (*condition*)

or

`do { `*instructions* } until (*notcondition*)

`for«each» «$i» (`*first* .. *last*) { *instructions* }

or

`for ($i = `*first*; $i <= *last*; $i++) { *instructions* }

`for«each» `*«$item»* (*set*) { *instructions* }

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`while `*condition* { *instructions* }

or

`until `*notcondition* { *instructions* }

`repeat { `*instructions* } while *condition*

or

`repeat { `*instructions* } until *notcondition*

`for `*first*..*last* -> $i { *instructions* }

or

`loop ($i = `*first*; $i <=*last*; $i++) { *instructions* }

`for `*set«* -> *$item»* { *instructions* }

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`while `*condition*

*instructions*

end

or

`until `*notcondition*

*instructions*

end

`begin`

*instructions*

end while *condition*

or

`begin`

*instructions*

end until *notcondition*

`for i in `*first*..*last*

*instructions*

end

or

`for i in `*first*...*last+1*

*instructions*

end

or

*first*.upto(*last*) { |i| *instructions* }

`for `*item* in *set*

*instructions*

end

or

*set*.each { |*item*| *instructions* }

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`while `*condition ;*do

*instructions*

done

or

`until `*notcondition ;*do

*instructions*

done

`for ((`*i* = *first*; *i* <= *last*; ++*i*)) ; do

*instructions*

done

`for `*item* in *set ;*do

*instructions*

done

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))`while (`*condition*) { *instructions* }

`do { `*instructions* } while (*condition*)

`for (`*i* <- *first* to *last* «by 1») { *instructions* }

or

*first* to *last* «by 1» foreach (*i* => { *instructions* })

`for (`*item* <- *set*) { *instructions* }

or

*set* foreach (*item* => { *instructions* })

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)*conditionBlock* whileTrue:

*loopBlock*

*loopBlock* doWhile:

*conditionBlock*

*first* to: *last* do:

*loopBlock*

*collection* do:

*loopBlock*

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(loop`

while *condition*

do

*instructions*)

or

`(do () (`*notcondition*)

*instructions*)

`(loop`

do

*instructions*

while *condition*)

`(loop`

for i from *first* to *last «by 1»*

do

*instructions*)

or

`(dotimes (i N)`

*instructions*)

or

`(do ((i `*first* `(1+ i))) ((>=i`

*last*))


*instructions*)

`(loop`

for *item* in *list*

do

*instructions*)

or

`(loop`

for *item* across *vector*

do

*instructions*)

or

`(dolist (`*item list*)

*instructions*)

or

`(mapc `*function list*)

or

`(map `*type function sequence*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(do () (`*notcondition*) *instructions*)

or

`(let loop () (if`

*condition* (begin *instructions* (loop))))

`(let loop () (`

*instructions* (if *condition* (loop))))

`(do ((i `*first* `(+ i 1))) ((>= i`

*last*)) *instructions*)

or

`(let loop ((i`

*first*`1)) (if (< i`

*last*) (begin *instructions* `(loop (+ i 1)))))`


`(for-each (lambda (`

*item*) *instructions*) *list*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(while `*condition instructions*)

`(tagbody loop`

*instructions* (if *condition* `(go loop))`


`(for ((i`

*first* `(+ i 1))) ((>= i`

*last*)) *instructions*)

`(mapc (lambda (`

*item*) *instructions*) *list*)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`while `*condition* do begin

*instructions*

end

`repeat`

*instructions*

until *notcondition*;

`for `*i* := *first* «step 1» to *last* do begin

*instructions*

end;

[[a]](https://en.wikipedia.org#endnote_step)`for `*item* in *set* do *instructions*

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Do While `*condition*

*instructions*

Loop

or

`Do Until `*notcondition*

*instructions*

Loop

or

`While `*condition*

*instructions*

Wend

(Visual Basic .NET uses `End While`

instead)
`Do`

*instructions*

Loop While *condition*

or

`Do`

*instructions*

Loop Until *notcondition*

`i`

must be declared beforehand.
`For `

*i* = *first* To *last* «Step *1» instructions*

Next i

`For Each `*item* In *set*

*instructions*

Next *item*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`For i« As `*type»* = *first* To *last«* Step *1»*

instructions

Next« i»

[[a]](https://en.wikipedia.org#endnote_step)`For Each `*item«* As *type»* In *set*

*instructions*

Next*« item»*

[Xojo](https://en.wikipedia.org/wiki/Xojo)`While `*condition*

*instructions*

Wend

`Do Until `*notcondition*

*instructions*

Loop

or

`Do`

*instructions*

Loop Until *notcondition*

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`while `*condition* :

`Tab ↹`*instructions*

«else:

`Tab ↹`*instructions»*

`for i in range(`

*first*, *last+1*):

`Tab ↹`*instructions*

«else:

`Tab ↹`*instructions»*

Python 2.x:

`for i in xrange(`

*first*, *last+1*):

`Tab ↹`*instructions*

«else:

`Tab ↹`*instructions»*

`for `*item* in *set*:

`Tab ↹`*instructions*

«else:

`Tab ↹`*instructions»*

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`while (`*condition*) { *instructions* } «then *optional-block»*

`do { `*instructions* } while (*condition*) «then *optional-block»*

`for (i = `*first*; i <= *last*; i++) { *instructions* } «then *optional-block»*

`foreach `*item*(*set*) «using (*what*)» { *instructions* } «then *optional-block»*

[Fortran](https://en.wikipedia.org/wiki/Fortran)`DO WHILE (`*condition*)

*instructions*

ENDDO

`DO`

*instructions*

IF (*condition*) EXIT

ENDDO

`DO `*I* = *first*,*last*

*instructions*

ENDDO

[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))`BEGIN `*«instructions» condition* WHILE *instructions* REPEAT

`BEGIN `* instructions condition* UNTIL

*limit start* DO *instructions* LOOP

[OCaml](https://en.wikipedia.org/wiki/OCaml)`while `*condition* do *instructions* done

`for i = `*first* to *last* do *instructions* done

`Array.iter (fun `*item* -> *instructions*) *array*

or

`List.iter (fun `*item* -> *instructions*) *list*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`while `*condition* do

`Tab ↹`*instructions*

`for i = `*first* to *last* do

`Tab ↹`*instructions*

`for `*item* in *set* do

`Tab ↹`*instructions*

or

`Seq.iter (fun `*item* -> *instructions*) *set*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`while `*condition* do ( *instructions* )

`Array.app (fn `*item* => *instructions*) *array*

or

`app (fn `*item* => *instructions*) *list*

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`Control.Monad.forM_ [`*first*..*last*] (\i -> do *instructions*)

`Control.Monad.forM_`*list* (\item -> do *instructions*)

[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))`from`

*setup*

until

*condition*

loop

*instructions*

end

[CoffeeScript](https://en.wikipedia.org/wiki/CoffeeScript)`while `*condition*

*expression*

or

*expression* while *condition*

or

`while `*condition* then *expression*

or

`until `*condition*

*expression*

or

*expression* until *condition*

or

`until `*expression* then *condition*

`for `*i* in [*first*..*last*]

*expression*

or

`for `*i* in [*first*..*last*] then *expression*

or

*expression* for *i* in [*first*..*last*]

`for `*item* in *set*

*expression*

or

`for `*item* in *set* then *expression*

or

*expression* for *item* in *set*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`PERFORM `*procedure-1* «THROUGH *procedure-2*» `««WITH» TEST BEFORE» UNTIL`

*condition*

[[c]](https://en.wikipedia.org#endnote_COBOL_THRU)or

`PERFORM ««WITH» TEST BEFORE» UNTIL`

*condition*

*expression*

END-PERFORM

`PERFORM `*procedure-1* «THROUGH *procedure-2*» `«WITH» TEST AFTER UNTIL`

*condition*

[[c]](https://en.wikipedia.org#endnote_COBOL_THRU)or

`PERFORM «WITH» TEST AFTER UNTIL`

*condition*

*expression*

END-PERFORM

`PERFORM `*procedure-1* «THROUGH *procedure-2»* VARYING *i* FROM *first* BY *increment* UNTIL *i* > *last*

[[d]](https://en.wikipedia.org#endnote_COBOL_GREATER_THAN)or

`PERFORM VARYING `*i* FROM *first* BY *increment* UNTIL *i* > *last*

*expression*

END-PERFORM

[[d]](https://en.wikipedia.org#endnote_COBOL_GREATER_THAN)[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`while `*condition* {

*expression*

}

`loop { `

*expression*

if *condition* {

break;

}

}

`for i in `*first*..*last+1* {

*expression*

}

or

`for i in `*first*..=*last* {

*expression*

}

`for `*item* in *set* {

*expression*

}

[[e]](https://en.wikipedia.org#endnote_Rust_FOREACH)or

*set*.into_iter().for_each(|*item*| expression);

[[e]](https://en.wikipedia.org#endnote_Rust_FOREACH)"[^a](https://en.wikipedia.org#ref_step)`step`

n" is used to change the loop interval. If "`step`

" is omitted, then the loop interval is 1.This implements the[^b](https://en.wikipedia.org#ref_Ada_quantifiers)[universal quantifier](https://en.wikipedia.org/wiki/Universal_quantifier)("for all" or ∀) as well as the[existential quantifier](https://en.wikipedia.org/wiki/Existential_quantifier)("there exists" or ∃).[^c](https://en.wikipedia.org#ref_COBOL_THRU)`THRU`

may be used instead of`THROUGH`

.[^d](https://en.wikipedia.org#ref_COBOL_GREATER_THAN)`«IS» GREATER «THAN»`

may be used instead of`>`

.Type of set expression must implement trait[^e](https://en.wikipedia.org#ref_Rust_FOREACH)`std::iter::IntoIterator`

.

| throw | handler | assertion | |
|---|---|---|---|
|

`raise `*exception_name* «with *string_expression»*

`begin`

*statements*

exception

when *exception_list*1 => *statements;*

when *exception_list*2 => *statements;*

*...*

«when others => *statements;*»

end

[[b]](https://en.wikipedia.org#endnote_Ada_uncaught_exceptions)`pragma Assert`

(«Check =>» *boolean_expression* ««Message =>» *string_expression*»)

*[function | procedure | entry]* with

Pre => *boolean_expression*

Post => *boolean_expression*

*any_type* with Type_Invariant => *boolean_expression*

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))*«string_expression»* ⎕SIGNAL *number_expression*

`:Trap `*number«s»_expression*

*statements*

«:Case *number«s»_expression*

*statements*»

*...*

«:Else *number«s»_expression*

*statements*»

:EndTrap

*«string_expression»* `⎕SIGNAL 98/⍨~`

*condition*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))[longjmp](https://en.wikipedia.org/wiki/Longjmp)(*state*, *exception*);

`switch (`[setjmp](https://en.wikipedia.org/wiki/Setjmp)(*state*)) { case 0: *instructions* break; case *exception*: *instructions* ... }

`assert(`*condition*);

[C++](https://en.wikipedia.org/wiki/C%2B%2B)`throw `*exception*;

`try { `*instructions* } catch «(*exception*)» { *instructions* } *...*

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`try { `*instructions* } catch «(*exception« name»*)» { *instructions* } *...* «finally { *instructions* }»

`System.Diagnostics.Debug.Assert(`*condition*);

or

`System.Diagnostics.Trace.Assert(`*condition*);

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`try { `*instructions* } catch (*exception*) { *instructions* } *...* «finally { *instructions* }»

`assert `*condition* «: *description*»;

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`try { `*instructions* } catch (*exception*) { *instructions*} «finally { *instructions* }»

[D](https://en.wikipedia.org/wiki/D_(programming_language))`try { `*instructions* } catch (*exception*) { *instructions* } *...* «finally { *instructions* }»

`assert(`*condition*);

[PHP](https://en.wikipedia.org/wiki/PHP)`try { `*instructions* } catch (*exception*) { *instructions* } *...* «finally { *instructions* }»

`assert(`*condition*);

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`try { `*instructions* } catch *«exception»* { *instructions* } *...* «finally { *instructions* }»

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`trap «[`*exception*]» { *instructions* } *... instructions*

or

`try { `*instructions* } catch «[*exception*]» { *instructions* } *...* «finally { *instructions* }»

`[Debug]::Assert(`

*condition*)

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`@throw `*exception*;

`@try { `*instructions* } @catch (*exception*) { *instructions* } *...* «@finally { *instructions* }»

`NSAssert(`*condition*, *description*);

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`throw `*exception*

(2.x)
`do { try `*expression* ... *instructions* } catch *exception* { *instructions* } *...*

(2.x)
`assert(`*condition*«, *description*»)

[Perl](https://en.wikipedia.org/wiki/Perl)`die `*exception*;

`eval { `*instructions* `}; if ($@) {`

*instructions* }

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`try { `*instructions* CATCH { when *exception* { *instructions* } *...*}}

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`raise `*exception*

`begin`

*instructions*

rescue *exception*

*instructions*

*...*

«else

*instructions*»

«ensure

*instructions*»

end

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)*exception* raise

*instructionBlock* on: *exception* do: *handlerBlock*

`assert: `*conditionBlock*

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(error `*"exception"*)

or

`(error`

*type*

*arguments*)

or

`(error (make-condition`

*type*

*arguments*))

`(handler-case`

(progn *instructions*)

(*exception instructions*)

*...*)

or

`(handler-bind`

(*condition*

(lambda

*instructions*

«invoke-restart *restart args»*))

*...*)

[[a]](https://en.wikipedia.org#endnote_a)`(assert `*condition*)

or

`(assert `*condition*

«(*place*)

*«error»»*)

or

`(check-type `*var type*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))([R](https://en.wikipedia.org/wiki/R6RS))6RS`(raise `*exception*)

`(guard (con (`*condition instructions*) *...*) *instructions*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(error `*"error-string" objects*)

or

`(signal-condition `*condition continuable*)

`(with-handler`

*handler form**

)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`raise `*Exception.Create()*

`try `*Except* on *E: exception* do begin *instructions* end; end;

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Err.Raise `*ERRORNUMBER*

`With New`

*Try*`: On Error Resume Next`


*OneInstruction*

.Catch`: On Error GoTo 0: Select Case`

*.Number*

Case *SOME_ERRORNUMBER*

*instructions*

`End Select: End With`


```
'*** Try class ***
Private mstrDescription As String
Private mlngNumber As Long
Public Sub Catch()
mstrDescription = Err.Description
mlngNumber = Err.Number
End Sub
Public Property Get Number() As Long
Number = mlngNumber
End Property
Public Property Get Description() As String
Description = mstrDescription
End Property
```

[[12]](https://en.wikipedia.org#cite_note-12)`Debug.Assert `*condition*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Throw `*exception*

or

`Error `*errorcode*

`Try`

*instructions*

Catch« *name* As *exception*»« When *condition*»

*instructions*

*...*

«Finally

*instructions*»

End Try

`System.Diagnostics.`Debug.Assert(*condition*)

or

`System.Diagnostics.`Trace.Assert(*condition*)

[Xojo](https://en.wikipedia.org/wiki/Xojo)`Raise `*exception*

`Try`

*instructions*

Catch *«exception»*

*instructions*

*...*

«Finally

*instructions*»

End Try

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`raise `*exception*

`try:`

`Tab ↹`*instructions*

except *«exception»*:

`Tab ↹`*instructions*

*...*

«else:

`Tab ↹`*instructions*»

«finally:

`Tab ↹`*instructions»*

`assert `*condition*

[Fortran](https://en.wikipedia.org/wiki/Fortran)[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))*code* THROW

*xt* CATCH *( code or 0 )*

[OCaml](https://en.wikipedia.org/wiki/OCaml)`raise `*exception*

`try `*expression* with *pattern* -> *expression ...*

`assert `*condition*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`try `*expression* with *pattern* -> *expression ...*

or

`try `*expression* finally *expression*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`raise `*exception «arg»*

*expression* handle *pattern* => *expression ...*

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`throw `*exception*

or

`throwError `*expression*

`catch `*tryExpression catchExpression*

or

`catchError `*tryExpression catchExpression*

`assert `*condition expression*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`RAISE «EXCEPTION»`

*exception*

`USE «AFTER» EXCEPTION OBJECT`

*class-name*.

or

`USE «AFTER» EO`

*class-name*.

or

`USE «AFTER» EXCEPTION CONDITION`

*exception-name* «FILE *file-name»*.

or

`USE «AFTER» EC`

*exception-name* «FILE *file-name»*.

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))[[13]](https://en.wikipedia.org#cite_note-13)`assert!(`*condition*)

Common Lisp allows[^a](https://en.wikipedia.org#ref_common_lisp_restarts)`with-simple-restart`

,`restart-case`

and`restart-bind`

to define restarts for use with`invoke-restart`

. Unhandled conditions may cause the implementation to show a restarts menu to the user before unwinding the stack.Uncaught exceptions are propagated to the innermost dynamically enclosing execution. Exceptions are not propagated across tasks (unless these tasks are currently synchronised in a rendezvous).[^b](https://en.wikipedia.org#ref_Ada_uncaught_exceptions)

### Other control flow statements

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=15)]

| exit block (break) | continue |
|
|---|

[goto](https://en.wikipedia.org/wiki/Goto))

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`exit `*«loop_name»* «when *condition»*

*label*:

`goto `*label*

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)*value* exit;

...
`do `*statements;* skip exit; *label: statements* od

`label:`

...
`go to `*label; ...*

goto *label; ...*

label; ...

`yield(value)`

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))`:Leave`

`:Continue`

*label*:

`→`*label*

or

`:GoTo `*label*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`break;`

`continue;`

*label*:

`goto `*label*;

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)[D](https://en.wikipedia.org/wiki/D_(programming_language))[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`yield return `*value*;

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`break `*«label»*;

`continue `*«label»*;

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`yield `*value«;»*

[PHP](https://en.wikipedia.org/wiki/PHP)`break `*«levels»*;

`continue `*«levels»*;

`goto `*label*;

`yield `*«key =>» value;*

[Perl](https://en.wikipedia.org/wiki/Perl)`last `*«label»*;

`next `*«label»*;

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`break `*«label»*

`continue `*«label»*

`goto `*label*

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`break `*«label»*

`continue `*«label»*

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`break `*«levels»*

`continue `*«levels»*

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(return)`

or

`(return-from `*block*)

or

`(loop-finish)`

`(tagbody `*tag*

*...*

*tag*

*...*)

`(go `*tag*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(return-from `*block*)

`(tagbody `*tag*

*...*

*tag*

*...*)

`(go `*tag*)

*label*:

[[a]](https://en.wikipedia.org#endnote_Pascal's_declarations)`goto `*label*;

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))([FPC](https://en.wikipedia.org/wiki/Free_Pascal))`break;`

`continue;`

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Exit `*block*

Alternatively, for methods,`Return`

*label*:

`GoTo `*label*

[Xojo](https://en.wikipedia.org/wiki/Xojo)`Continue `*block*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Yield `*value*

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`break`

`continue`

`yield `*value*

[RPG IV](https://en.wikipedia.org/wiki/RPG_IV)`LEAVE;`

`ITER;`

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`break;`

`continue;`

[Fortran](https://en.wikipedia.org/wiki/Fortran)`EXIT`

`CYCLE`

`label`

[[b]](https://en.wikipedia.org#endnote_Fortran_label)`GOTO `*label*

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`break`

`next`

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`break `*«label»*

`continue`

[OCaml](https://en.wikipedia.org/wiki/OCaml)[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))[COBOL](https://en.wikipedia.org/wiki/COBOL)`EXIT PERFORM`

or `EXIT PARAGRAPH`

or `EXIT SECTION`

or `EXIT.`

`EXIT PERFORM CYCLE`

*label* «SECTION».

`GO TO `*label*

See * reflective programming* for calling and declaring functions by strings.

| calling a function | basic/void function | value-returning function | required
|
|---|

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)*foo «(parameters)»*

`procedure `*foo «(parameters)»* is begin *statements* end *foo*

`function `*foo «(parameters)»* return *type* is begin *statements* end *foo*

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)*foo «(parameters)»*;

`proc `*foo* = *«(parameters)»* [void](https://en.wikipedia.org/wiki/Void_type): ( *instructions* );

`proc `*foo* = *«(parameters)»* rettype: ( *instructions ...; retvalue* );

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))*«parameters»* foo *parameters*

*foo←*{ *statements* }

*foo←*{ *statements* }

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))*foo*(*«parameters»*)

[void](https://en.wikipedia.org/wiki/Void_type) *foo*(*«parameters»*) { *instructions* }

*type* *foo*(*«parameters»*) { *instructions ...* return *value*; }

*«global declarations»*

`int main(«int argc, char *argv[]»)`

{

*instructions*

}

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`public static void main(String[] args)`

{ *instructions* }

or

`public static void main(String`

[...](https://en.wikipedia.org/wiki/Variadic_function) args) { *instructions* }

[D](https://en.wikipedia.org/wiki/D_(programming_language))`int main(«char[][] args»)`

{ *instructions*}

or

`int main(«string[] args»)`

{ *instructions*}

or

`void main(«char[][] args»)`

{ *instructions*}

or

`void main(«string[] args»)`

{ *instructions*}

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))[void](https://en.wikipedia.org/wiki/Void_type) foo(*«parameters»*) => *statement*;

[void](https://en.wikipedia.org/wiki/Void_type) foo(*«parameters»*) => *expression*;

`static void Main(«string[] args») method_body`

May instead return

`int`

.(starting with C# 7.1:) May return

`Task`

or `Task<int>`

, and if so, may be `async`

.
[JavaScript](https://en.wikipedia.org/wiki/JavaScript)`function foo(`*«parameters»*) { *instructions* }

or

`var foo = function (`

*«parameters»*) { *instructions* }

or

`var foo = new Function (`

*"«parameter»"*, *...*, *"«last parameter»"* "*instructions*");

`function foo(`*«parameters»*) { *instructions ...* return *value*; }

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`func foo(`*«parameters»*) { *instructions* }

`func foo(`*«parameters»*) *type* { *instructions ...* return *value* }

`func main() { `*instructions* }

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`func foo(`*«parameters»*) { *instructions* }

`func foo(`*«parameters»*) -> *type* { *instructions ...* return *value* }

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(foo `*«parameters»*)

`(`[defun](https://en.wikipedia.org/wiki/Defun) foo (*«parameters»*)

*instructions*)

or

`(setf (symbol-function '`

*symbol*)

*function*)

`(`[defun](https://en.wikipedia.org/wiki/Defun) foo (*«parameters»*)

*...*

value)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(define (foo `*parameters*) *instructions*)

or

`(define foo (`[lambda](https://en.wikipedia.org/wiki/Anonymous_function) (*parameters*) *instructions*))

`(define (foo `*parameters*) *instructions... return_value*)

or

`(define foo (`[lambda](https://en.wikipedia.org/wiki/Anonymous_function) (*parameters*) *instructions... return_value*))

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(`[defun](https://en.wikipedia.org/wiki/Defun) foo (*«parameters»*)

*instructions*)

`(`[defun](https://en.wikipedia.org/wiki/Defun) foo (*«parameters»*)

*...*

value)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`foo«(`*parameters*)»

`procedure foo«(`*parameters*)»; «forward;»[[a]](https://en.wikipedia.org#endnote_forward_declaration)

«label

*label declarations*»

«const

*constant declarations*»

«type

*type declarations*»

«var

*variable declarations»*

«local function declarations»

begin

*instructions*

end;

`function foo«(`*parameters*)»: *type*; «forward;»[[a]](https://en.wikipedia.org#endnote_forward_declaration)

«label

*label declarations*»

«const

*constant declarations*»

«type

*type declarations*»

«var

*variable declarations»*

«local function declarations»

begin

*instructions*;

foo := *value*

end;

`program `*name*;

«label

*label declarations*»

«const

*constant declarations*»

«type

*type declarations*»

«var

*variable declarations»*

«function declarations»

begin

*instructions*

end.

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Foo(`*«parameters»*)

`Sub Foo«(`*parameters*)»

*instructions*

End Sub

`Function Foo«(`*parameters*)»« As* type»*

*instructions*

Foo = *value*

End Function

`Sub Main()`

*instructions*

End Sub

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Function Foo«(`

*parameters*)»« As *type»*

*instructions*

Return *value*

End Function

The `As`

clause is not required if `Option Strict`

is off. A type character may be used instead of the `As`

clause.

If control exits the function without a return value having been explicitly specified, the function returns the default value for the return type.

`Sub Main(««ByVal »args() As String»)`


*instructions*

End Sub

or`Function Main(««ByVal »args() As String») As Integer`


*instructions*

End Function

[Xojo](https://en.wikipedia.org/wiki/Xojo)[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`foo(`*«parameters»*)

`def foo(`*«parameters»*):

`Tab ↹`*instructions*

`def foo(`*«parameters»*):

`Tab ↹`*instructions*

`Tab ↹`return *value*

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`foo(`*«parameters» «;qualifiers»*)

`define foo (`*«parameters»*) { *instructions* }

`define foo (`*«parameters»*) { *instructions ...* return *value*; }

`public define slsh_main () { `*instructions* }

[Fortran](https://en.wikipedia.org/wiki/Fortran)`foo (`*«arguments»*)

CALL sub_foo (*«arguments»*)

[[c]](https://en.wikipedia.org#endnote_Fortran_arguments)`SUBROUTINE sub_foo (`*«arguments»*)

*instructions*

END SUBROUTINE

[[c]](https://en.wikipedia.org#endnote_Fortran_arguments)*type* FUNCTION foo (*«arguments»*)

*instructions*

*...*

*foo* = *value*

END FUNCTION

[[c]](https://en.wikipedia.org#endnote_Fortran_arguments)`PROGRAM `*main*

*instructions*

END PROGRAM

[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))*«parameters» *FOO

`: FOO « stack effect comment:`

(* before* -- ) »

*instructions*

;

`: FOO « stack effect comment:`

(* before* -- *after* ) »

*instructions*

;

[PHP](https://en.wikipedia.org/wiki/PHP)`foo(`*«parameters»*)

`function foo(`*«parameters»*) { *instructions* }

`function foo(`*«parameters»*) { *instructions* ... return *value*; }

[Perl](https://en.wikipedia.org/wiki/Perl)`foo(`*«parameters»*)

or

`&foo«(`*parameters*)»

`sub foo { «my (`

*parameters*) = @_;» *instructions *}

`sub foo { «my (`

*parameters*) = @_;» *instructions*... «return» *value*; }

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`foo(`*«parameters»*)

or

`&foo«(`*parameters*)»

`«multi »sub foo(`

*parameters*) { *instructions* }

`«our «`*type*» »`«multi »sub foo(`

*parameters*) { *instructions ...* «return» *value*; }

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`foo«(`*parameters*)»

`def foo«(`*parameters*)»

*instructions*

end

`def foo«(`*parameters*)»

*instructions*

«return» *value*

end

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))`foo(`*«parameters»*)

`fn foo(`*«parameters»*) { *instructions* }

`fn foo(`*«parameters»*) -> *type* { *instructions* }

`fn main() { `*instructions* }

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))*foo*«(*parameters*)»

`def `*foo*«(*parameters*)»«: Unit =» { *instructions* }

`def `*foo*«(*parameters*)»«: *type»* = { *instructions ...* «return» *value* }

`def main(args: Array[String])`

{ *instructions* }

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`foo `*«parameters»*

`function `*foo* { *instructions* };

or

`function `*foo* { «param(*parameters*)» *instructions* }

`function `*foo* «(*parameters*)» { *instructions ...* return *value* };

or

`function foo { «param(`*parameters*)» *instructions ...* return *value* }

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`foo `*«parameters»*

`function foo {`

*instructions*

}

or

`foo () {`

*instructions*

}

`function foo {`

*instructions*

return *«exit_code»*

}

or

`foo () { `

*instructions*

return *«exit_code»*

}

- parameters
`$`

(*n**$1*,*$2*,*$3*, ...)`$@`

(all parameters)`$#`

(the number of parameters)`$0`

(this function name)


[OCaml](https://en.wikipedia.org/wiki/OCaml)`foo `*parameters*

`let «rec» foo `*parameters* = *instructions*

`let «rec» foo `*parameters* = *instructions... return_value*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`[<EntryPoint>] let main args`

=* instructions*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`fun foo `*parameters* = ( *instructions* )

`fun foo `*parameters* = ( *instructions... return_value* )

[Haskell](https://en.wikipedia.org/wiki/Haskell)`foo `*parameters* = do

`Tab ↹`*instructions*

`foo `*parameters* = *return_value*

or

`foo `*parameters* = do

`Tab ↹`*instructions*

`Tab ↹`return *value*

`«main :: IO ()»`

main = do *instructions*

[Eiffel](https://en.wikipedia.org/wiki/Eiffel_(programming_language))`foo (`*«parameters»*)

`foo (`*«parameters»*)

require

*preconditions*

do

*instructions*

ensure

*postconditions*

end

`foo (`*«parameters»*)*: type*

require

*preconditions*

do

*instructions*

Result *:= value*

ensure

*postconditions*

end

[[b]](https://en.wikipedia.org#endnote_root_class_and_feature)[CoffeeScript](https://en.wikipedia.org/wiki/CoffeeScript)`foo()`

`foo = ->`

`foo = ->`

*value*

`foo `*parameters*

`foo = () ->`

`foo = ( `*parameters* ) -> *value*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`CALL "`*foo*" «USING *parameters»*

«exception-handling»

«END-CALL*»*

[[d]](https://en.wikipedia.org#endnote_COBOL_calling_programs)`«IDENTIFICATION DIVISION.»`

PROGRAM-ID. *foo*.

«other divisions...»

PROCEDURE DIVISION *«*USING *parameters»*.

instructions.

`«IDENTIFICATION DIVISION.»`

PROGRAM-ID/FUNCTION-ID. *foo*.

«*other divisions...*»

DATA DIVISION.

«*other sections...*»

LINKAGE SECTION.

«*parameter definitions...*»

*variable-to-return definition*

«*other sections...*»

PROCEDURE DIVISION «USING *parameters»* RETURNING *variable-to-return*.

*instructions*.

`«FUNCTION» `*foo«(«parameters»)»*

Pascal requires "[^a](https://en.wikipedia.org#ref_forward_declaration)`forward;`

" for[forward declarations](https://en.wikipedia.org/wiki/Forward_declaration).Eiffel allows the specification of an application's root class and feature.[^b](https://en.wikipedia.org#ref_root_class_and_feature)In Fortran, function/subroutine parameters are called arguments (since[^c](https://en.wikipedia.org#ref_Fortran_arguments)`PARAMETER`

is a language keyword); the`CALL`

keyword is required for subroutines.Instead of using[^d](https://en.wikipedia.org#ref_COBOL_calling_programs)`"foo"`

, a string variable may be used instead containing the same value.

Where *string* is a signed decimal number:

| string to integer | string to long integer | string to floating point | integer to string | floating point to string | |
|---|---|---|---|---|---|
|

`Integer'Value (`*string_expression*)

`Long_Integer'Value (`*string_expression*)

`Float'Value (`*string_expression*)

`Integer'Image (`*integer_expression*)

`Float'Image (`*float_expression*)

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)with general, and then specific formats`string `*buf := "12345678.9012e34 ";* file *proxy; associate(proxy, buf);*

`get(proxy, ivar);`

`get(proxy, livar);`

`get(proxy, rvar);`

`put(proxy, ival);`

`put(proxy, rval);`

`getf(proxy, ($g$, ivar));`

or

`getf(proxy, ($dddd$, ivar));`

`getf(proxy, ($g$, livar));`

or

`getf(proxy, ($8d$, livar));`

`getf(proxy, ($g$, rvar));`

or

`getf(proxy, ($8d.4dE2d$, rvar));`

`putf(proxy, ($g$, ival));`

or

`putf(proxy, ($4d$, ival));`

`putf(proxy, ($g(width, places, exp)$, rval));`

or

`putf(proxy, ($8d.4dE2d$, rval));`

[APL](https://en.wikipedia.org/wiki/APL_(programming_language))`⍎`*string_expression*

`⍎`*string_expression*

`⍎`*string_expression*

`⍕`*integer_expression*

`⍕`*float_expression*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))*integer* = [atoi](https://en.wikipedia.org/wiki/Atoi)(*string*);

*long* = [atol](https://en.wikipedia.org/wiki/Atol_(programming))(*string*);

*float* = [atof](https://en.wikipedia.org/wiki/Atof)(*string*);

[sprintf](https://en.wikipedia.org/wiki/Sprintf)(*string*, "%i", *integer*);

[sprintf](https://en.wikipedia.org/wiki/Sprintf)(*string*, "%f", *float*);

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)*integer* = [*string* intValue];

*long* = [*string* longLongValue];

*float* = [*string* doubleValue];

*string* = `[NSString stringWithFormat:@"%i",`

*integer*];

*string* = `[NSString stringWithFormat:@"%f",`

*float*];

[C++](https://en.wikipedia.org/wiki/C%2B%2B)(STL)`«std::»istringstream(`*string*) >> *number;*

`«std::»ostringstream `*o*; *o* << *number*; *string* = *o*.str();

[C++11](https://en.wikipedia.org/wiki/C%2B%2B11)*integer* = «*std::*»stoi(*string*);

*long* = «*std::*»stol(*string*);

*float* = «*std::*»stof(*string); double* = «*std::*»stod(*string*);

*string* = «*std::*»to_string(*number*);

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))*integer* = int.Parse(*string*);

*long* = long.Parse(*string*);

*float* = float.Parse(*string*);

*double* = double.Parse(*string*);

*string* = *number*.ToString();

[D](https://en.wikipedia.org/wiki/D_(programming_language))*integer* = std.conv.to!int(*string*)

*long* = std.conv.to!long(*string*)

*float* = std.conv.to!float(*string*)

*double* = std.conv.to!double(*string*)

*string* = std.conv.to!string(*number*)

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))*integer* = Integer.parseInt(*string*);

*long* = Long.parseLong(*string*);

*float* = Float.parseFloat(*string*);

*double* = Double.parseDouble(*string*);

*string* = Integer.toString(*integer*);

*string* = String.valueOf(*integer*);

*string* = Float.toString(*float*);

*string* = Double.toString(*double*);

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[[a]](https://en.wikipedia.org#endnote_JavaScript's_technicalities)*integer* = parseInt(*string*);

*float* = parseFloat(*string*);

*float* = new Number (*string*);

*float* = Number (*string*);

*float* = +*string;*

*string* = *number*.toString ();

*string* = String (*number*);

*string* = *number*+"";

*string* = `${*number*}`

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))*integer*, *error* = strconv.Atoi(*string*)

*integer*, *error* = strconv.ParseInt(*string*, 10, 0)

*long*, *error* = strconv.ParseInt(*string*, 10, 64)

*float*, *error* = strconv.ParseFloat(*string*, 64)

*string* = strconv.Itoa(*integer*)

*string* = strconv.FormatInt(*integer*, 10)

*string* = fmt.Sprint(*integer*)

*string* = strconv.FormatFloat(*float*)

*string* = fmt.Sprint(*float*)

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))[[d]](https://en.wikipedia.org#endnote_Rust_type_conversion)*string*.parse::<i32>()

`i32::from_str(`*string*)

*string*.parse::<i64>()

`i64::from_str(`*string*)

*string*.parse::<f64>()

`f64::from_str(`*string*)

*integer*.to_string()

*float*.to_string()

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(setf `*integer* (parse-integer *string*))

`(setf `*float* (read-from-string *string*))

`(setf `*string* (princ-to-string *number*))

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(define `*number* (string->number *string*))

`(define `*string* (number->string *number*))

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(setf `*integer* (convert *string* <integer>))

`(setf `*float* (convert *string* <float>))

`(setf `*string* (convert *number* <string>))

*integer* := StrToInt(*string*);

*float* := StrToFloat(*string*);

*string* := IntToStr(*integer*);

*string* := FloatToStr(*float*);

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))*integer* = CInt(*string*)

*long* = CLng(*string*)

*float* = CSng(*string*)

*double* = CDbl(*string*)

*string* = CStr(*number*)

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)(can use both VB syntax above and .NET methods shown right)

*integer* = Integer.Parse(*string*)

*long* = Long.Parse(*string*)

*float* = Single.Parse(*string*)

*double* = Double.Parse(*string*)

*string* =* number*.ToString()

[Xojo](https://en.wikipedia.org/wiki/Xojo)*integer* = Val(*string*)

*long* = Val(*string*)

*double* = Val(*string*)

*double* = CDbl(*string*)

*string* = CStr(*number*)

or

*string* = Str(*number*)

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))*integer* = int(*string*)

*long* = long(*string*)

*float* = float(*string*)

*string* = str(*number*)

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)*integer* = [atoi](https://en.wikipedia.org/wiki/Atoi)(*string*);

*long* = [atol](https://en.wikipedia.org/wiki/Atol_(programming))(*string*);

*float* = [atof](https://en.wikipedia.org/wiki/Atof)(*string*);

*string* = string(*number*);

[Fortran](https://en.wikipedia.org/wiki/Fortran)`READ(`*string*,*format*) *number*

`WRITE(`*string*,*format*) *number*

[PHP](https://en.wikipedia.org/wiki/PHP)*integer* = intval(*string*);

or

*integer* = (int)*string*;

*float* = floatval(*string*);

*float* = (float)*string*;

*string* = "*$number*";

or

*string* = strval(*number*);

or

*string* = (string)*number*;

[Perl](https://en.wikipedia.org/wiki/Perl)[[b]](https://en.wikipedia.org#endnote_Perl's_technicalities)*number* = 0 + *string;*

*string* = "*number*";

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))*number* = +*string;*

*string* = ~*number*;

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))*integer* = *string*.to_i

or

*integer* = Integer(*string*)

*float* = *string*.to_f

*float* = Float(*string*)

*string* = *number*.to_s

[Scala](https://en.wikipedia.org/wiki/Scala_(programming_language))*integer* = *string*.toInt

*long* = *string*.toLong

*float* = *string*.toFloat

*double* = *string*.toDouble

*string* = *number*.toString

[Smalltalk](https://en.wikipedia.org/wiki/Smalltalk)*integer := Integer* readFrom: *string*

*float := Float* readFrom: *string*

*string := number *asString

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)*integer* = [int]*string*

*long* = [long]*string*

*float* = [float]*string*

*string* = [string]*number*;

or

*string* = "*number*";

or

*string* = (*number*).ToString()

[OCaml](https://en.wikipedia.org/wiki/OCaml)`let `*integer* = int_of_string *string*

`let `*float* = float_of_string *string*

`let `*string* = string_of_int *integer*

`let `*string* = string_of_float *float*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`let `*integer* = int *string*

`let `*integer* = int64 *string*

`let `*float* = float *string*

`let `*string* = string *number*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`val `*integer* = Int.fromString *string*

`val `*float* = Real.fromString *string*

`val `*string* = Int.toString *integer*

`val `*string* = Real.toString *float*

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))*number* = read *string*

*string* = show *number*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`MOVE «FUNCTION» NUMVAL(`

*string*)[[c]](https://en.wikipedia.org#endnote_COBOL's_NUMVAL_alternatives) TO *number*

`MOVE `*number* TO *numeric-edited*

JavaScript only uses floating point numbers so there are some technicalities.[^a](https://en.wikipedia.org#ref_JavaScript's_technicalities)[[7]](https://en.wikipedia.org#cite_note-Javascript_numbers-7)Perl doesn't have separate types. Strings and numbers are interchangeable.[^b](https://en.wikipedia.org#ref_Perl's_technicalities)[^c](https://en.wikipedia.org#ref_COBOL's_NUMVAL_alternatives)`NUMVAL-C`

or`NUMVAL-F`

may be used instead of`NUMVAL`

.[^](https://en.wikipedia.org#ref_Rust_type_conversion)is available to convert any type that has an implementation of the`str::parse`

trait. Both`std::str::FromStr`

`str::parse`

andreturn a`FromStr::from_str`

that contains the specified type if there is no error. The`Result`

[turbofish](https://en.wikipedia.org/w/index.php?title=Turbofish&action=edit&redlink=1)(`::<_>`

) on`str::parse`

can be omitted if the type can be inferred from context.

| read from | write to | ||
|---|---|---|---|
|

[stdout](https://en.wikipedia.org/wiki/Stdout)

[stderr](https://en.wikipedia.org/wiki/Stderr)

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)`Get (`*x*)

`Put (`*x*)

`Put (Standard_Error, `*x*)

[ALGOL 68](https://en.wikipedia.org/wiki/ALGOL_68)`readf((`*$format$*, *x*));

or

`getf(stand in, (`*$format$*, *x*));

[printf](https://en.wikipedia.org/wiki/Printf)((*$format$*, *x*));

or

`putf(stand out, (`*$format$*, *x*));

`putf(stand error, (`*$format$*, *x*));

[[a]](https://en.wikipedia.org#endnote_ALGOL_Unformatted)[APL](https://en.wikipedia.org/wiki/APL_(programming_language))*x←*⎕

`⎕←`*x*

`⍞←`*x*

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))[scanf](https://en.wikipedia.org/wiki/Scanf)(*format*, &*x*);

or

[fscanf](https://en.wikipedia.org/wiki/Fscanf)(stdin, *format*, &*x*);

[[b]](https://en.wikipedia.org#endnote_more_c_input)[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*);

or

[fprintf](https://en.wikipedia.org/wiki/Fprintf)(stdout, *format*, *x*);

[[c]](https://en.wikipedia.org#endnote_more_c_output)[fprintf](https://en.wikipedia.org/wiki/Fprintf)(stderr, *format*, *x*);

[[d]](https://en.wikipedia.org#endnote_more_c_error_output)[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`data = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];`

`[[NSFileHandle fileHandleWithStandardOutput] writeData:data];`

`[[NSFileHandle fileHandleWithStandardError] writeData:data];`

[C++](https://en.wikipedia.org/wiki/C%2B%2B)[«std::»cin](https://en.wikipedia.org/wiki/Iostream) >> *x*;

or

`«std::»getline(«std::»cin, `*str*);

[«std::»cout](https://en.wikipedia.org/wiki/Iostream) << *x*;

[«std::»cerr](https://en.wikipedia.org/wiki/Iostream) << *x*;

or

[«std::»clog](https://en.wikipedia.org/wiki/Iostream) << *x*;

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))*x* = Console.Read();

or

*x* = Console.ReadLine();

`Console.Write(`*«format*, »*x*);

or

`Console.WriteLine(`*«format*, »*x*);

`Console.Error`.Write(*«format*, »*x*);

or

`Console.Error`.WriteLine(*«format*, »*x*);

[D](https://en.wikipedia.org/wiki/D_(programming_language))*x* = std.stdio.readln()

`std.stdio.write(`*x*)

or

`std.stdio.writeln(`*x*)

or

`std.stdio.writef(`*format*, *x*)

or

`std.stdio.writefln(`*format*, *x*)

`stderr.write(`*x*)

or

`stderr.writeln(`*x*)

or

`std.stdio`.writef(stderr, *format*, *x*)

or

`std.stdio`.writefln(stderr, *format*, *x*)

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`x = System.in.read();`

or

`x = new Scanner(System.in).nextInt();`

or

`x = new Scanner(System.in).nextLine();`

`System.out.print(`*x*);

or

`System.out.`[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*);

or

`System.out.println(`*x*);

`System.err.print(`*x*);

or

`System.err.`[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*);

or

`System.err.println(`*x*);

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`fmt.Scan(&`*x*)

or

`fmt.`[Scanf](https://en.wikipedia.org/wiki/Scanf)(*format*, &*x*)

or

`x = bufio.NewReader(os.Stdin).ReadString('\n')`

`fmt.Println(`*x*)

or

`fmt.`[Printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*)

`fmt.Fprintln(os.Stderr, x)`

or

`fmt.`[Fprintf](https://en.wikipedia.org/wiki/Fprintf)(os.Stderr, *format*, *x*)

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))*x* = readLine()

(2.x)
`print(`*x*)

(2.x)`println(`*x*)

(1.x)
[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[Web Browser implementation](https://en.wikipedia.org/wiki/Client-side_JavaScript)`document.write(`*x*)

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[Active Server Pages](https://en.wikipedia.org/wiki/Active_Server_Pages)`Response.Write(`*x*)

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[Windows Script Host](https://en.wikipedia.org/wiki/Windows_Script_Host)*x* = WScript.StdIn.Read(*chars*)

or

*x* = WScript.StdIn.ReadLine()

`WScript.Echo(`*x*)

or

`WScript.StdOut.Write(`*x*)

or

`WScript.StdOut.WriteLine(`*x*)

`WScript.StdErr.Write(`*x*)

or

`WScript.StdErr.WriteLine(`*x*)

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(setf x (read-line))`

`(princ `*x*)

or

`(format t `*format x*)

`(princ x *error-output*)`

or

`(format *error-output*`

*format x*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))([R](https://en.wikipedia.org/wiki/R6RS))6RS`(define x (read-line))`

`(display `*x*)

or

`(format #t`

*format x*)

`(display x (current-error-port))`

or

`(format (current-error-port)`

*format x*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)`(setf x (read-line))`

`(format (standard-output)`

*format x*)

`(format (error-output)`

*format x*)

[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`read(`*x*);

or

`readln(`*x*);

`write(`*x*);

or

`writeln(`*x*);

`write(stderr, `*x*);

or

`writeln(stderr, `*x*);

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Input« `*prompt*,» *x*

`Print `*x*

or

`? `*x*

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)*x* = Console.Read()

or

*x* = Console.ReadLine()

`Console.Write(`*«format*,»*x*)

or

`Console.WriteLine(`*«format*, »*x*)

`Console.Error`.Write(*«format*, *»x*)

or

`Console.Error`.WriteLine(*«format*, »*x*)

[Xojo](https://en.wikipedia.org/wiki/Xojo)*x* = StandardInputStream.Read()

or

*x* = StandardInputStreame.ReadLine()

`StandardOutputStream.Write(`*x*)

or

`StandardOutputStream.WriteLine(`*x*)

`StdErr.Write(`*x*)

or

`StdErr.WriteLine(`*x*)

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))2.x*x* = raw_input(*«prompt»*)

`print `*x*

or

`sys.stdout.write(`*x*)

`print >> sys.stderr,`

*x*

or

`sys.stderr.write(`*x*)

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))3.x*x* = input(*«prompt»*)

`print(`*x«*, end=""»)

`print(`*x«*, end=""», file=sys.stderr)

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)[fgets](https://en.wikipedia.org/wiki/Fgets) (&*x*, stdin)

[fputs](https://en.wikipedia.org/wiki/Fputs) (*x*, stdout)

[fputs](https://en.wikipedia.org/wiki/Fputs) (*x*, stderr)

[Fortran](https://en.wikipedia.org/wiki/Fortran)`READ(*,`*format*) *variable names*

or

`READ(INPUT_UNIT,`*format*) *variable names*

[[e]](https://en.wikipedia.org#endnote_Fortran_standard_units)`WRITE(*,`*format*) *expressions*

or

`WRITE(OUTPUT_UNIT,`*format*) *expressions*

[[e]](https://en.wikipedia.org#endnote_Fortran_standard_units)`WRITE(ERROR_UNIT,`*format*) *expressions*

[[e]](https://en.wikipedia.org#endnote_Fortran_standard_units)[Forth](https://en.wikipedia.org/wiki/Forth_(programming_language))*buffer length* ACCEPT *( # chars read )*

KEY *( char )*

*buffer length* TYPE

*char* EMIT

[PHP](https://en.wikipedia.org/wiki/PHP)*$x* = [fgets](https://en.wikipedia.org/wiki/Fgets)(STDIN);

or

*$x* = [fscanf](https://en.wikipedia.org/wiki/Fscanf)(STDIN, *format*);

`print `*x*;

or

[echo](https://en.wikipedia.org/wiki/Echo_(command)) *x*;

or

[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*);

[fprintf](https://en.wikipedia.org/wiki/Fprintf)(STDERR, *format*, *x*);

[Perl](https://en.wikipedia.org/wiki/Perl)*$x* = <>;

or

*$x* = <STDIN>;

`print `*x*;

or

[printf](https://en.wikipedia.org/wiki/Printf) *format*, *x*;

`print STDERR `*x*;

or

[printf](https://en.wikipedia.org/wiki/Printf) STDERR *format*, *x*;

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`$x = $*IN.get;`

*x*.print

or

*x*.say

*x*.note

or

`$*ERR.print(x)`

or

`$*ERR.say(x)`

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))*x* = gets

`puts `*x*

or

[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*)

`$stderr.puts(x)`

or

`$stderr.`[printf](https://en.wikipedia.org/wiki/Printf)(*format*, *x*)

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)*$x* = Read-Host«« -Prompt» *text*»;

or

`$x = [Console]::Read();`

or

`$x = [Console]::ReadLine()`

*x*;

or

`Write-Output `*x*;

or

`echo `*x*

`Write-Error `*x*

[OCaml](https://en.wikipedia.org/wiki/OCaml)`let `*x* = read_int ()

or

`let `*str* = read_line ()

or

`Scanf.`[scanf](https://en.wikipedia.org/wiki/Scanf) *format* (fun *x ...* -> *...*)

`print_int `*x*

or

`print_endline `*str*

or

`Printf.`[printf](https://en.wikipedia.org/wiki/Printf) *format x ...*

`prerr_int `*x*

or

`prerr_endline `*str*

or

`Printf.`[eprintf](https://en.wikipedia.org/wiki/Fprintf) *format x ...*

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`let x = System.Console.ReadLine()`

[printf](https://en.wikipedia.org/wiki/Printf) *format x ...*

or

[printfn](https://en.wikipedia.org/wiki/Printf) *format x ...*

[eprintf](https://en.wikipedia.org/wiki/Fprintf) *format x ...*

or

[eprintfn](https://en.wikipedia.org/wiki/Fprintf) *format x ...*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`val str = TextIO.inputLIne TextIO.stdIn`

`print `*str*

`TextIO.output (TextIO.stdErr,`

* str*)

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))*x* <- readLn

or

*str* <- getLine

`print `*x*

or

`putStrLn `*str*

`hPrint stderr `*x*

or

`hPutStrLn stderr `*str*

[COBOL](https://en.wikipedia.org/wiki/COBOL)`ACCEPT `*x*

`DISPLAY `*x*

ALGOL 68 additionally as the "unformatted"[^a](https://en.wikipedia.org#ref_ALGOL_Unformatted)[transput](https://en.wikipedia.org/wiki/Transput)routines:`read`

,`write`

,`get`

, and`put`

.[^b](https://en.wikipedia.org#ref_more_c_input)

and[gets](https://en.wikipedia.org/wiki/Gets())(x)

read unformatted text from stdin. Use of gets is not recommended.[fgets](https://en.wikipedia.org/wiki/Fgets)(x,*length*, stdin)[^c](https://en.wikipedia.org#ref_more_c_input)

and[puts](https://en.wikipedia.org/wiki/Puts_(C))(x)

write unformatted text to stdout.[fputs](https://en.wikipedia.org/wiki/Fputs)(x, stdout)[^d](https://en.wikipedia.org#ref_more_c_error_output)`fputs(x, stderr)`

writes unformatted text to stderrINPUT_UNIT, OUTPUT_UNIT, ERROR_UNIT are defined in the ISO_FORTRAN_ENV module.[^e](https://en.wikipedia.org#ref_Fortran_standard_units)[[15]](https://en.wikipedia.org#cite_note-15)

## Reading [command-line arguments](https://en.wikipedia.org/wiki/Command-line_argument)

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=19)]

| Argument values | Argument counts | Program name / Script name | |
|---|---|---|---|
|

`Argument (`*n*)

`Argument_Count`

`Command_Name`

[C](https://en.wikipedia.org/wiki/C_(programming_language))([C99](https://en.wikipedia.org/wiki/C99))`argv[`*n*]

`argc`

[Objective-C](https://en.wikipedia.org/wiki/Objective-C)[C++](https://en.wikipedia.org/wiki/C%2B%2B)[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`args[`*n*]

`args.Length`

`Assembly.GetEntryAssembly()`.Location;

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`args.length`

[D](https://en.wikipedia.org/wiki/D_(programming_language))[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[Windows Script Host](https://en.wikipedia.org/wiki/Windows_Script_Host)implementation`WScript.Arguments(`*n*)

`WScript.Arguments.length`

`WScript.ScriptName`

or

`WScript.ScriptFullName`

[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`os.Args[`*n*]

`len(os.Args)`

[Rust](https://en.wikipedia.org/wiki/Rust_(programming_language))[[a]](https://en.wikipedia.org#endnote_Rust_args)`std::env::args().nth(`*n*)

`std::env::args_os().nth(`*n*)

`std::env::args().count()`

`std::env::args_os().count()`

`std::env::args().next()`

`std::env::args_os().next()`

[Swift](https://en.wikipedia.org/wiki/Swift_(programming_language))`Process.arguments[`*n*]

or`Process.unsafeArgv[`*n*]

`Process.arguments.count`

or`Process.argc`

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))([R](https://en.wikipedia.org/wiki/R6RS))6RS`(list-ref (command-line) n)`

`(length (command-line))`

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`ParamStr(`*n*)

`ParamCount`

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Command`

[[b]](https://en.wikipedia.org#endnote_unseparated)`App.Path`

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`CmdArgs(`*n*)

`CmdArgs.Length`

`[Assembly].GetEntryAssembly().Location`

[Xojo](https://en.wikipedia.org/wiki/Xojo)`System.CommandLine`

`Application.ExecutableFile.Name`

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`sys.argv[`*n*]

`len(sys.argv)`

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`__argv[`*n*]

`__argc`

[Fortran](https://en.wikipedia.org/wiki/Fortran)`DO `*i* = *1*,*argc*

CALL GET_COMMAND_ARGUMENT (*i*,*argv(i)*)

ENDDO

*argc* = COMMAND_ARGUMENT_COUNT ()

`CALL GET_COMMAND_ARGUMENT (`*0*,*progname*)

[PHP](https://en.wikipedia.org/wiki/PHP)`$argv[`*n*]

`$argc`

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)`$`*n* ($1, $2, $3, *...*)

`$@`

(all arguments)
`$#`

`$0`

[Perl](https://en.wikipedia.org/wiki/Perl)`$ARGV[`*n*]

`scalar(@ARGV)`

`$0`

[Raku](https://en.wikipedia.org/wiki/Raku_(programming_language))`@*ARGS[`*n*]

`@*ARGS.elems`

`$PROGRAM_NAME`

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`ARGV[`*n*]

`ARGV.size`

`$0`

[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`$args[`*n*]

`$args.Length`

`$MyInvocation.MyCommand`.Name

[OCaml](https://en.wikipedia.org/wiki/OCaml)`Sys.argv.(`*n*)

`Array.length Sys.argv`

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))`args.[`*n*]

`args.Length`

`Assembly.GetEntryAssembly()`.Location

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`List.nth (CommandLine.arguments (), n)`

`length (CommandLine.arguments ())`

`CommandLine.name ()`

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`do { args <- System.getArgs; return length args !! n`

}
`do { args <- System.getArgs; return length args`

}
`System.getProgName`

[COBOL](https://en.wikipedia.org/wiki/COBOL)[[c]](https://en.wikipedia.org#endnote_COBOL_Arguments)In Rust,[^a](https://en.wikipedia.org#ref_Rust_args)`std::env::args`

and`std::env::args_os`

return iterators,`std::env::Args`

and`std::env::ArgsOs`

respectively.`Args`

converts each argument to a`String`

and it panics if it reaches an argument that cannot be converted to[UTF-8](https://en.wikipedia.org/wiki/UTF-8).`ArgsOs`

returns a non-lossy representation of the raw strings from the operating system (`std::ffi::OsString`

), which can be invalid UTF-8.In Visual Basic, command-line arguments are not separated. Separating them requires a split function[^b](https://en.wikipedia.org#ref_unseparated)`Split(`

.*string*)The COBOL standard includes no means to access command-line arguments, but common compiler extensions to access them include defining parameters for the main program or using[^c](https://en.wikipedia.org#ref_COBOL_Arguments)`ACCEPT`

statements.

## Execution of commands

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=20)]

| Shell command | Execute program |
|
|---|

[Ada](https://en.wikipedia.org/wiki/Ada_(programming_language))[[1]](https://en.wikipedia.org#cite_note-Ada_RM_2012-1)[POSIX](https://en.wikipedia.org/wiki/POSIX).[[16]](https://en.wikipedia.org#cite_note-Ada_Execute_Command-16)[C](https://en.wikipedia.org/wiki/C_(programming_language))[system](https://en.wikipedia.org/wiki/System_(C_standard_library))("*command*");

[execl](https://en.wikipedia.org/wiki/Exec_(operating_system))(*path*, *args*);

or

[execv](https://en.wikipedia.org/wiki/Exec_(operating_system))(*path*, *arglist*);

[C++](https://en.wikipedia.org/wiki/C%2B%2B)[Objective-C](https://en.wikipedia.org/wiki/Objective-C)`[NSTask launchedTaskWithLaunchPath:(NSString *)path arguments:(NSArray *)arguments];`

[C#](https://en.wikipedia.org/wiki/C_Sharp_(programming_language))`System.Diagnostics`.Process.Start(*path*, *argstring*);

[F#](https://en.wikipedia.org/wiki/F_Sharp_(programming_language))[Go](https://en.wikipedia.org/wiki/Go_(programming_language))`exec.Run(`*path*, *argv*, *envv*, *dir*, exec.DevNull, exec.DevNull, exec.DevNull)

`os.Exec(`*path*, *argv*, *envv*)

[Visual Basic](https://en.wikipedia.org/wiki/Visual_Basic_(classic))`Interaction.Shell(`*command* «, *WindowStyle*» «, *isWaitOnReturn*»)

[Visual Basic .NET](https://en.wikipedia.org/wiki/Visual_Basic_.NET)`Microsoft.VisualBasic`.Interaction.Shell(*command* «, *WindowStyle*» «, *isWaitOnReturn*»)

`System.Diagnostics`.Process.Start(*path*, *argstring*)

[Xojo](https://en.wikipedia.org/wiki/Xojo)`Shell.Execute(`*command* «, *Parameters*»)

`FolderItem.Launch(`*parameters*, *activate*)

[D](https://en.wikipedia.org/wiki/D_(programming_language))`std.process.system("`*command*");

`std.process.execv(`*path*, *arglist*);

[Java](https://en.wikipedia.org/wiki/Java_(programming_language))`Runtime.exec(`*command*);

or

`new ProcessBuilder(command).start();`

[JavaScript](https://en.wikipedia.org/wiki/JavaScript)[Windows Script Host](https://en.wikipedia.org/wiki/Windows_Script_Host)implementation`WScript.CreateObject ("WScript.Shell").Run(`

*command* «, *WindowStyle*» «, *isWaitOnReturn*»);

`WshShell.Exec(command)`

[Common Lisp](https://en.wikipedia.org/wiki/Common_Lisp)`(uiop:run-program `*command*)

[Scheme](https://en.wikipedia.org/wiki/Scheme_(programming_language))`(system `*command*)

[ISLISP](https://en.wikipedia.org/wiki/ISLISP)[Pascal](https://en.wikipedia.org/wiki/Pascal_(programming_language))`system(`*command*);

[OCaml](https://en.wikipedia.org/wiki/OCaml)`Sys.command `*command*, Unix.open_process_full *command env (stdout, stdin, stderr),...*

`Unix.create_process `*prog args new_stdin new_stdout new_stderr, ...*

`Unix.execv `*prog args*

or

`Unix.execve `*prog args env*

[Standard ML](https://en.wikipedia.org/wiki/Standard_ML)`OS.Process.system `*command*

`Unix.execute (`*path*, *args*)

`Posix.Process.exec (`*path*, *args*)

[Haskell](https://en.wikipedia.org/wiki/Haskell)([GHC](https://en.wikipedia.org/wiki/Glasgow_Haskell_Compiler))`System.system `*command*

`System.Process`.runProcess *path args ...*

`Posix.Process`.executeFile *path* True *args ...*

[Perl](https://en.wikipedia.org/wiki/Perl)`system(`*command*)

or

*$output* = `*command*`

or

*$output* = qx(*command*)

`exec(`*path*, *args*)

[Ruby](https://en.wikipedia.org/wiki/Ruby_(programming_language))`system(`*command*)

or

*output* = `*command*`

`exec(`*path*, *args*)

[PHP](https://en.wikipedia.org/wiki/PHP)`system(`*command*)

or

*$output* = `*command*`

or

`exec(`*command*)

or

`passthru(`*command*)

[Python](https://en.wikipedia.org/wiki/Python_(programming_language))`os.system(`*command*)

or

`subprocess.Popen(`*command*)

`subprocess.call(`*["program", "arg1", "arg2", ...]*)

`os.execv(`*path*, *args*)

[S-Lang](https://en.wikipedia.org/wiki/S-Lang)`system(`*command*)

[Fortran](https://en.wikipedia.org/wiki/Fortran)`CALL EXECUTE_COMMAND_LINE (`*COMMAND* «, *WAIT*» «, *EXITSTAT*» «, *CMDSTAT*» «, *CMDMSG*»)

[[a]](https://en.wikipedia.org#endnote_Fortran_2008)[Windows PowerShell](https://en.wikipedia.org/wiki/Windows_PowerShell)`[Diagnostics.Process]::Start(command)`

`«Invoke-Item »`*program arg1 arg2 ...*

[Bash shell](https://en.wikipedia.org/wiki/Bash_shell)*output*=`*command*`

or

*output*=$(*command*)

`program arg1 arg2 ...`

## See also

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=21)]

## References

[[edit](https://en.wikipedia.org/w/index.php?title=Comparison_of_programming_languages_(basic_instructions)&action=edit§ion=22)]

- ^
**a****b****c****d****e****f****g****h****i****j****k****l****m****n****o**Ada Reference Manual – Language and Standard Libraries; ISO/IEC 8652:201x (E),**p**["Reference Manual"](https://web.archive.org/web/20110427190723/http://www.ada-auth.org/standards/12rm/RM-Final.pdf)(PDF). Archived from[the original](http://www.ada-auth.org/standards/12rm/RM-Final.pdf)(PDF) on 2011-04-27. Retrieved 2013-07-19. [^](https://en.wikipedia.org#cite_ref-HyperSpec_2-0)["Common Lisp HyperSpec (TM)"](http://www.lispworks.com/documentation/HyperSpec/Front/index.htm).*lispworks.com*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-Specification_3-0)["www.islisp.info: Specification"](https://web.archive.org/web/20160122121427/http://islisp.info/specification.html).*islisp.info*. Archived from[the original](http://www.islisp.info/specification.html)on 22 January 2016. Retrieved 30 January 2017.- ^
**a****b**["selected_int_kind in Fortran Wiki"](http://fortranwiki.org/fortran/show/selected_int_kind).*fortranwiki.org*. Retrieved 30 January 2017. [^](https://en.wikipedia.org#cite_ref-5)["Erlang — Types and Function Specifications"](http://www.erlang.org/doc/reference_manual/typespec.html).*erlang.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-6)["Erlang — Advanced"](http://www.erlang.org/doc/efficiency_guide/advanced.html).*erlang.org*. Retrieved 30 January 2017.- ^
**a****b**[8.5 The Number Type](https://www.mozilla.org/js/language/E262-3.pdf) - ^
**a****b**["selected_real_kind in Fortran Wiki"](http://fortranwiki.org/fortran/show/selected_real_kind).*fortranwiki.org*. Retrieved 30 January 2017. [^](https://en.wikipedia.org#cite_ref-9)["The GNU C Library: Complex Numbers"](https://www.gnu.org/software/libc/manual/html_node/Complex-Numbers.html#Complex-Numbers).*gnu.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-10)["Grammar vb"](https://ljw1004.github.io/vbspec/vb.html).*Visual Basic Language Specification*. 2016-06-17.[Archived](https://web.archive.org/web/20190829225051/https://ljw1004.github.io/vbspec/vb.html)from the original on 2019-08-29. Retrieved 2019-08-29.[^](https://en.wikipedia.org#cite_ref-11)["for...of"](https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Statements/for...of).*mozilla.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-12)["Try-Catch for VB"](https://web.archive.org/web/20160416093023/https://sites.google.com/site/truetryforvisualbasic/).*google.com*. Archived from[the original](https://sites.google.com/site/truetryforvisualbasic/)on 16 April 2016. Retrieved 30 January 2017.Klabnik, Steve; Nichols, Carol.[^](https://en.wikipedia.org#cite_ref-13)["Error Handling"](https://doc.rust-lang.org/book/ch09-00-error-handling.html)..*The Rust Programming Language*[^](https://en.wikipedia.org#cite_ref-14)["Prime decomposition – Rosetta Code"](http://rosettacode.org/wiki/Prime_decomposition#ALGOL_68).*rosettacode.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-15)["iso_fortran_env in Fortran Wiki"](http://fortranwiki.org/fortran/show/iso_fortran_env).*fortranwiki.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-Ada_Execute_Command_16-0)["Execute a system command – Rosetta Code"](http://rosettacode.org/wiki/Execute_a_system_command#Ada).*rosettacode.org*. Retrieved 30 January 2017.[^](https://en.wikipedia.org#cite_ref-17)["EXECUTE_COMMAND_LINE – The GNU Fortran Compiler"](https://gcc.gnu.org/onlinedocs/gfortran/EXECUTE_005fCOMMAND_005fLINE.html).*gnu.org*. Retrieved 30 January 2017.