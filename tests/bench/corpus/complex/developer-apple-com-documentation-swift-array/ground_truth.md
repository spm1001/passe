# Array
*Structure*

An ordered, random-access collection.

**Availability:** iOS 8.0 | iPadOS 8.0 | Mac Catalyst 13.0 | macOS 10.10 | tvOS 9.0 | visionOS 1.0 | watchOS 2.0

```swift
@frozen struct Array<Element>
```

## Overview

Arrays are one of the most commonly used data types in an app. You use arrays to organize your app’s data. Specifically, you use the `Array` type to hold elements of a single type, the array’s `Element` type. An array can store any kind of elements—from integers to strings to classes.

Swift makes it easy to create arrays in your code using an array literal: simply surround a comma-separated list of values with square brackets. Without any other information, Swift creates an array that includes the specified values, automatically inferring the array’s `Element` type. For example:

```swift
// An array of 'Int' elements
let oddNumbers = [1, 3, 5, 7, 9, 11, 13, 15]

// An array of 'String' elements
let streets = ["Albemarle", "Brandywine", "Chesapeake"]
```

You can create an empty array by specifying the `Element` type of your array in the declaration. For example:

```swift
// Shortened forms are preferred
var emptyDoubles: [Double] = []

// The full type name is also allowed
var emptyFloats: Array<Float> = Array()
```

If you need an array that is preinitialized with a fixed number of default values, use the `Array(repeating:count:)` initializer.

```swift
var digitCounts = Array(repeating: 0, count: 10)
print(digitCounts)
// Prints "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
```

# Accessing Array Values

When you need to perform an operation on all of an array’s elements, use a `for`-`in` loop to iterate through the array’s contents.

```swift
for street in streets {
    print("I don't live on \(street).")
}
// Prints "I don't live on Albemarle."
// Prints "I don't live on Brandywine."
// Prints "I don't live on Chesapeake."
```

Use the `isEmpty` property to check quickly whether an array has any elements, or use the `count` property to find the number of elements in the array.

```swift
if oddNumbers.isEmpty {
    print("I don't know any odd numbers.")
} else {
    print("I know \(oddNumbers.count) odd numbers.")
}
// Prints "I know 8 odd numbers."
```

Use the `first` and `last` properties for safe access to the value of the array’s first and last elements. If the array is empty, these properties are `nil`.

```swift
if let firstElement = oddNumbers.first, let lastElement = oddNumbers.last {
    print(firstElement, lastElement, separator: ", ")
}
// Prints "1, 15"

print(emptyDoubles.first, emptyDoubles.last, separator: ", ")
// Prints "nil, nil"
```

You can access individual array elements through a subscript. The first element of a nonempty array is always at index zero. You can subscript an array with any integer from zero up to, but not including, the count of the array. Using a negative number or an index equal to or greater than `count` triggers a runtime error. For example:

```swift
print(oddNumbers[0], oddNumbers[3], separator: ", ")
// Prints "1, 7"

print(emptyDoubles[0])
// Triggers runtime error: Index out of range
```

# Adding and Removing Elements

Suppose you need to store a list of the names of students that are signed up for a class you’re teaching. During the registration period, you need to add and remove names as students add and drop the class.

```swift
var students = ["Ben", "Ivy", "Jordell"]
```

To add single elements to the end of an array, use the `append(_:)` method. Add multiple elements at the same time by passing another array or a sequence of any kind to the `append(contentsOf:)` method.

```swift
students.append("Maxime")
students.append(contentsOf: ["Shakia", "William"])
// ["Ben", "Ivy", "Jordell", "Maxime", "Shakia", "William"]
```

You can add new elements in the middle of an array by using the `insert(_:at:)` method for single elements and by using `insert(contentsOf:at:)` to insert multiple elements from another collection or array literal. The elements at that index and later indices are shifted back to make room.

```swift
students.insert("Liam", at: 3)
// ["Ben", "Ivy", "Jordell", "Liam", "Maxime", "Shakia", "William"]
```

To remove elements from an array, use the `remove(at:)`, `removeSubrange(_:)`, and `removeLast()` methods.

```swift
// Ben's family is moving to another state
students.remove(at: 0)
// ["Ivy", "Jordell", "Liam", "Maxime", "Shakia", "William"]

// William is signing up for a different class
students.removeLast()
// ["Ivy", "Jordell", "Liam", "Maxime", "Shakia"]
```

You can replace an existing element with a new value by assigning the new value to the subscript.

```swift
if let i = students.firstIndex(of: "Maxime") {
    students[i] = "Max"
}
// ["Ivy", "Jordell", "Liam", "Max", "Shakia"]
```

## Growing the Size of an Array

Every array reserves a specific amount of memory to hold its contents. When you add elements to an array and that array begins to exceed its reserved capacity, the array allocates a larger region of memory and copies its elements into the new storage. The new storage is a multiple of the old storage’s size. This exponential growth strategy means that appending an element happens in constant time, averaging the performance of many append operations. Append operations that trigger reallocation have a performance cost, but they occur less and less often as the array grows larger.

If you know approximately how many elements you will need to store, use the `reserveCapacity(_:)` method before appending to the array to avoid intermediate reallocations. Use the `capacity` and `count` properties to determine how many more elements the array can store without allocating larger storage.

For arrays of most `Element` types, this storage is a contiguous block of memory. For arrays with an `Element` type that is a class or `@objc` protocol type, this storage can be a contiguous block of memory or an instance of `NSArray`. Because any arbitrary subclass of `NSArray` can become an `Array`, there are no guarantees about representation or efficiency in this case.

# Modifying Copies of Arrays

Each array has an independent value that includes the values of all of its elements. For simple types such as integers and other structures, this means that when you change a value in one array, the value of that element does not change in any copies of the array. For example:

```swift
var numbers = [1, 2, 3, 4, 5]
var numbersCopy = numbers
numbers[0] = 100
print(numbers)
// Prints "[100, 2, 3, 4, 5]"
print(numbersCopy)
// Prints "[1, 2, 3, 4, 5]"
```

If the elements in an array are instances of a class, the semantics are the same, though they might appear different at first. In this case, the values stored in the array are references to objects that live outside the array. If you change a reference to an object in one array, only that array has a reference to the new object. However, if two arrays contain references to the same object, you can observe changes to that object’s properties from both arrays. For example:

```swift
// An integer type with reference semantics
class IntegerReference {
    var value = 10
}
var firstIntegers = [IntegerReference(), IntegerReference()]
var secondIntegers = firstIntegers

// Modifications to an instance are visible from either array
firstIntegers[0].value = 100
print(secondIntegers[0].value)
// Prints "100"

// Replacements, additions, and removals are still visible
// only in the modified array
firstIntegers[0] = IntegerReference()
print(firstIntegers[0].value)
// Prints "10"
print(secondIntegers[0].value)
// Prints "100"
```

Arrays, like all variable-size collections in the standard library, use copy-on-write optimization. Multiple copies of an array share the same storage until you modify one of the copies. When that happens, the array being modified replaces its storage with a uniquely owned copy of itself, which is then modified in place. Optimizations are sometimes applied that can reduce the amount of copying.

This means that if an array is sharing storage with other copies, the first mutating operation on that array incurs the cost of copying the array. An array that is the sole owner of its storage can perform mutating operations in place.

In the example below, a `numbers` array is created along with two copies that share the same storage. When the original `numbers` array is modified, it makes a unique copy of its storage before making the modification. Further modifications to `numbers` are made in place, while the two copies continue to share the original storage.

```swift
var numbers = [1, 2, 3, 4, 5]
var firstCopy = numbers
var secondCopy = numbers

// The storage for 'numbers' is copied here
numbers[0] = 100
numbers[1] = 200
numbers[2] = 300
// 'numbers' is [100, 200, 300, 4, 5]
// 'firstCopy' and 'secondCopy' are [1, 2, 3, 4, 5]
```

# Bridging Between Array and NSArray

When you need to access APIs that require data in an `NSArray` instance instead of `Array`, use the type-cast operator (`as`) to bridge your instance. For bridging to be possible, the `Element` type of your array must be a class, an `@objc` protocol (a protocol imported from Objective-C or marked with the `@objc` attribute), or a type that bridges to a Foundation type.

The following example shows how you can bridge an `Array` instance to `NSArray` to use the `write(to:atomically:)` method. In this example, the `colors` array can be bridged to `NSArray` because the `colors` array’s `String` elements bridge to `NSString`. The compiler prevents bridging the `moreColors` array, on the other hand, because its `Element` type is `Optional<String>`, which does  bridge to a Foundation type.

```swift
let colors = ["periwinkle", "rose", "moss"]
let moreColors: [String?] = ["ochre", "pine"]

let url = URL(fileURLWithPath: "names.plist")
(colors as NSArray).write(to: url, atomically: true)
// true

(moreColors as NSArray).write(to: url, atomically: true)
// error: cannot convert value of type '[String?]' to type 'NSArray'
```

Bridging from `Array` to `NSArray` takes O(1) time and O(1) space if the array’s elements are already instances of a class or an `@objc` protocol; otherwise, it takes O() time and space.

When the destination array’s element type is a class or an `@objc` protocol, bridging from `NSArray` to `Array` first calls the `copy(with:)` (`- copyWithZone:` in Objective-C) method on the array to get an immutable copy and then performs additional Swift bookkeeping work that takes O(1) time. For instances of `NSArray` that are already immutable, `copy(with:)` usually returns the same array in O(1) time; otherwise, the copying performance is unspecified. If `copy(with:)` returns the same array, the instances of `NSArray` and `Array` share storage using the same copy-on-write optimization that is used when two instances of `Array` share storage.

When the destination array’s element type is a nonclass type that bridges to a Foundation type, bridging from `NSArray` to `Array` performs a bridging copy of the elements to contiguous storage in O() time. For example, bridging from `NSArray` to `Array<Int>` performs such a copy. No further bridging is required when accessing elements of the `Array` instance.

## Creating an Array

- **init()** — Creates a new, empty array.
- **init(_:)** — Creates a new instance of a collection containing the elements of a sequence.
- **init(_:)** — Creates an array containing the elements of a sequence.
- **init(repeating:count:)** — Creates a new array containing the specified number of a single, repeated value.
- **init(unsafeUninitializedCapacity:initializingWith:)** — Creates an array with the specified capacity, and then calls the given closure with a buffer covering the array’s uninitialized memory.
## Inspecting an Array

- **isEmpty** — A Boolean value indicating whether the collection is empty.
- **count** — The number of elements in the array.
- **capacity** — The total number of elements that the array can contain without allocating new storage.
## Accessing Elements

- **subscript(_:)** — Accesses the element at the specified position.
- **first** — The first element of the collection.
- **last** — The last element of the collection.
- **subscript(_:)** — Accesses a contiguous subrange of the array’s elements.
- **subscript(_:)**
- **subscript(_:)** — Accesses the contiguous subrange of the collection’s elements specified by a range expression.
- **subscript(_:)**
- **randomElement()** — Returns a random element of the collection.
- **randomElement(using:)** — Returns a random element of the collection, using the given generator as a source for randomness.
## Adding Elements

- **append(_:)** — Adds a new element at the end of the array.
- **insert(_:at:)** — Inserts a new element at the specified position.
- **insert(contentsOf:at:)** — Inserts the elements of a sequence into the collection at the specified position.
- **replaceSubrange(_:with:)** — Replaces a range of elements with the elements in the specified collection.
- **replaceSubrange(_:with:)** — Replaces the specified subrange of elements with the given collection.
- **reserveCapacity(_:)** — Reserves enough space to store the specified number of elements.
## Combining Arrays

- **append(contentsOf:)** — Adds the elements of a sequence to the end of the array.
- **append(contentsOf:)** — Adds the elements of a sequence or collection to the end of this collection.
- **+(_:_:)** — Creates a new collection by concatenating the elements of a sequence and a collection.
- **+(_:_:)** — Creates a new collection by concatenating the elements of a collection and a sequence.
- **+(_:_:)**
- **+(_:_:)** — Creates a new collection by concatenating the elements of two collections.
- **+=(_:_:)** — Appends the elements of a sequence to a range-replaceable collection.
- **+=(_:_:)**
## Removing Elements

- **remove(at:)** — Removes and returns the element at the specified position.
- **removeFirst()** — Removes and returns the first element of the collection.
- **removeFirst(_:)** — Removes the specified number of elements from the beginning of the collection.
- **removeLast()** — Removes and returns the last element of the collection.
- **removeLast(_:)** — Removes the specified number of elements from the end of the collection.
- **removeSubrange(_:)** — Removes the elements in the specified subrange from the collection.
- **removeSubrange(_:)** — Removes the elements in the specified subrange from the collection.
- **removeAll(where:)** — Removes all the elements that satisfy the given predicate.
- **removeAll(keepingCapacity:)** — Removes all elements from the array.
- **popLast()** — Removes and returns the last element of the collection.
## Finding Elements

- **contains(_:)** — Returns a Boolean value indicating whether the sequence contains the given element.
- **contains(where:)** — Returns a Boolean value indicating whether the sequence contains an element that satisfies the given predicate.
- **allSatisfy(_:)** — Returns a Boolean value indicating whether every element of a sequence satisfies a given predicate.
- **first(where:)** — Returns the first element of the sequence that satisfies the given predicate.
- **firstIndex(of:)** — Returns the first index where the specified value appears in the collection.
- **index(of:)** — Returns the first index where the specified value appears in the collection.
- **firstIndex(where:)** — Returns the first index in which an element of the collection satisfies the given predicate.
- **last(where:)** — Returns the last element of the sequence that satisfies the given predicate.
- **lastIndex(of:)** — Returns the last index where the specified value appears in the collection.
- **lastIndex(where:)** — Returns the index of the last element in the collection that matches the given predicate.
- **min()** — Returns the minimum element in the sequence.
- **min(by:)** — Returns the minimum element in the sequence, using the given predicate as the comparison between elements.
- **max()** — Returns the maximum element in the sequence.
- **max(by:)** — Returns the maximum element in the sequence, using the given predicate as the comparison between elements.
## Selecting Elements

- **prefix(_:)** — Returns a subsequence, up to the specified maximum length, containing the initial elements of the collection.
- **prefix(through:)** — Returns a subsequence from the start of the collection through the specified position.
- **prefix(upTo:)** — Returns a subsequence from the start of the collection up to, but not including, the specified position.
- **prefix(while:)** — Returns a subsequence containing the initial elements until `predicate` returns `false` and skipping the remaining elements.
- **suffix(_:)** — Returns a subsequence, up to the given maximum length, containing the final elements of the collection.
- **suffix(from:)** — Returns a subsequence from the specified position to the end of the collection.
## Excluding Elements

- **dropFirst(_:)** — Returns a subsequence containing all but the given number of initial elements.
- **dropLast(_:)** — Returns a subsequence containing all but the specified number of final elements.
- **drop(while:)** — Returns a subsequence by skipping elements while `predicate` returns `true` and returning the remaining elements.
## Transforming an Array

- **flatMap(_:)** — Returns an array containing the concatenated results of calling the given transformation with each element of this sequence.
- **flatMap(_:)**
- **compactMap(_:)** — Returns an array containing the non-`nil` results of calling the given transformation with each element of this sequence.
- **reduce(_:_:)** — Returns the result of combining the elements of the sequence using the given closure.
- **reduce(into:_:)** — Returns the result of combining the elements of the sequence using the given closure.
- **lazy** — A sequence containing the same elements as this sequence, but on which some operations, such as `map` and `filter`, are implemented lazily.
## Iterating Over an Array’s Elements

- **forEach(_:)** — Calls the given closure on each element in the sequence in the same order as a `for`-`in` loop.
- **enumerated()** — Returns a sequence of pairs (, ), where  represents a consecutive integer starting at zero and  represents an element of the sequence.
- **makeIterator()** — Returns an iterator over the elements of the collection.
- **underestimatedCount** — A value less than or equal to the number of elements in the collection.
## Reordering an Array’s Elements

- **sort()** — Sorts the collection in place.
- **sort(by:)** — Sorts the collection in place, using the given predicate as the comparison between elements.
- **sorted()** — Returns the elements of the sequence, sorted.
- **sorted(by:)** — Returns the elements of the sequence, sorted using the given predicate as the comparison between elements.
- **reverse()** — Reverses the elements of the collection in place.
- **reversed()** — Returns a view presenting the elements of the collection in reverse order.
- **shuffle()** — Shuffles the collection in place.
- **shuffle(using:)** — Shuffles the collection in place, using the given generator as a source for randomness.
- **shuffled()** — Returns the elements of the sequence, shuffled.
- **shuffled(using:)** — Returns the elements of the sequence, shuffled using the given generator as a source for randomness.
- **partition(by:)** — Reorders the elements of the collection such that all the elements that match the given predicate are after all the elements that don’t match.
- **swapAt(_:_:)** — Exchanges the values at the specified indices of the collection.
## Splitting and Joining Elements

- **split(separator:maxSplits:omittingEmptySubsequences:)** — Returns the longest possible subsequences of the collection, in order, around elements equal to the given element.
- **split(maxSplits:omittingEmptySubsequences:whereSeparator:)** — Returns the longest possible subsequences of the collection, in order, that don’t contain elements satisfying the given predicate.
- **joined()** — Returns the elements of this sequence of sequences, concatenated.
- **joined(separator:)** — Returns the concatenated elements of this sequence of sequences, inserting the given separator between each element.
- **joined(separator:)** — Returns a new string by concatenating the elements of the sequence, adding the given separator between each element.
- **joined(separator:)** — Returns a new string by concatenating the elements of the sequence, adding the given separator between each element.
## Creating and Applying Differences

- **applying(_:)** — Applies the given difference to this collection.
- **difference(from:)** — Returns the difference needed to produce this collection’s ordered elements from the given collection.
- **difference(from:by:)** — Returns the difference needed to produce this collection’s ordered elements from the given collection, using the given predicate as an equivalence test.
## Comparing Arrays

- **==(_:_:)** — Returns a Boolean value indicating whether two arrays contain the same elements in the same order.
- **!=(_:_:)** — Returns a Boolean value indicating whether two values are not equal.
- **elementsEqual(_:)** — Returns a Boolean value indicating whether this sequence and another sequence contain the same elements in the same order.
- **elementsEqual(_:by:)** — Returns a Boolean value indicating whether this sequence and another sequence contain equivalent elements in the same order, using the given predicate as the equivalence test.
- **starts(with:)** — Returns a Boolean value indicating whether the initial elements of the sequence are the same as the elements in another sequence.
- **starts(with:by:)** — Returns a Boolean value indicating whether the initial elements of the sequence are equivalent to the elements in another sequence, using the given predicate as the equivalence test.
- **lexicographicallyPrecedes(_:)** — Returns a Boolean value indicating whether the sequence precedes another sequence in a lexicographical (dictionary) ordering, using the less-than operator (`<`) to compare elements.
- **lexicographicallyPrecedes(_:by:)** — Returns a Boolean value indicating whether the sequence precedes another sequence in a lexicographical (dictionary) ordering, using the given predicate to compare elements.
## Manipulating Indices

- **startIndex** — The position of the first element in a nonempty array.
- **endIndex** — The array’s “past the end” position—that is, the position one greater than the last valid subscript argument.
- **index(after:)** — Returns the position immediately after the given index.
- **formIndex(after:)** — Replaces the given index with its successor.
- **index(before:)** — Returns the position immediately before the given index.
- **formIndex(before:)** — Replaces the given index with its predecessor.
- **index(_:offsetBy:)** — Returns an index that is the specified distance from the given index.
- **formIndex(_:offsetBy:)** — Offsets the given index by the specified distance.
- **index(_:offsetBy:limitedBy:)** — Returns an index that is the specified distance from the given index, unless that distance is beyond a given limiting index.
- **formIndex(_:offsetBy:limitedBy:)** — Offsets the given index by the specified distance, or so that it equals the given limiting index.
- **distance(from:to:)** — Returns the distance between two indices.
## Accessing Underlying Storage

- **withUnsafeBufferPointer(_:)** — Calls a closure with a pointer to the array’s contiguous storage.
- **withUnsafeMutableBufferPointer(_:)** — Calls the given closure with a pointer to the array’s mutable contiguous storage.
- **withUnsafeBytes(_:)** — Calls the given closure with a pointer to the underlying bytes of the array’s contiguous storage.
- **withUnsafeMutableBytes(_:)** — Calls the given closure with a pointer to the underlying bytes of the array’s mutable contiguous storage.
- **withContiguousStorageIfAvailable(_:)** — Executes a closure on the sequence’s contiguous storage.
- **withContiguousMutableStorageIfAvailable(_:)** — Executes a closure on the collection’s contiguous storage.
## Encoding and Decoding

- **encode(to:)** — Encodes the elements of this array into the given encoder in an unkeyed container.
- **init(from:)** — Creates a new array by decoding from the given decoder.
## Describing an Array

- **description** — A textual representation of the array and its elements.
- **debugDescription** — A textual representation of the array and its elements, suitable for debugging.
- **customMirror** — A mirror that reflects the array.
- **hash(into:)** — Hashes the essential components of this value by feeding them into the given hasher.
## Converting Between Arrays and Create ML Types

- **init(_:)** — Constructs an Array with the elements of a DataColumn.
- **init(_:)** — Constructs an Array with the elements of an MLUntypedColumn.
## Related Array Types

- **ContiguousArray** — A contiguously stored array.
- **ArraySlice** — A slice of an `Array`, `ContiguousArray`, or `ArraySlice` instance.
## Reference Types

- **NSArray** — A static ordered collection of objects.
- **NSMutableArray** — A dynamic ordered collection of objects.
## Supporting Types

- **Array.Index** — The index type for arrays, `Int`.
- **Array.Indices** — The type that represents the indices that are valid for subscripting an array, in ascending order.
- **Array.Iterator** — The type that allows iteration over an array’s elements.
- **Array.ArrayLiteralElement** — The type of the elements of an array literal.
- **Array.SubSequence** — A collection representing a contiguous subrange of this collection’s elements. The subsequence shares indices with the original collection.
## Infrequently Used Functionality

- **init(arrayLiteral:)** — Creates an array from the given array literal.
- **hashValue** — The hash value.
## Initializers

- **init(capacity:initializingWith:)** — Creates an array with the specified capacity, and then calls the given closure with an output span covering the array’s uninitialized memory.
- **init(fromSplitComplex:scale:count:)** — Creates a new array of single-precision values from a `DSPSplitComplex` structure.
- **init(fromSplitComplex:scale:count:)** — Creates a new array of single-precision values from a `DSPDoubleSplitComplex` structure.
## Instance Properties

- **mutableSpan**
- **span**
## Instance Methods

- **append(addingCapacity:initializingWith:)** — Grows the array to have enough capacity for the specified number of elements, then calls the closure with an output span covering the array’s uninitialized memory.
- **withUnsafeTaggedBuffers(_:)** — Access the underlying CMTaggedBuffers.
## Type Aliases

- **Array.Specification**
- **Array.UnderlyingSequence**
- **Array.UnwrappedType**
- **Array.ValueType**
## Type Properties

- **defaultResolverSpecification**
## Type Methods

- **monoscopicForVideoOutput()** — Creates a collection of CMTags with the required tags to describe monoscopic video, where there is no stereo view, e.g. kCMTagStereoNone.
- **stereoscopicForVideoOutput()** — Creates a collection of CMTags with the required tags to describe basic stereoscopic video, where both left and right stereo eyes are present, e.g. kCMTagStereoLeftAndRight.
## Default Implementations

- **Attachable Implementations**
- **BidirectionalCollection Implementations**
- **Collection Implementations**
- **CustomDebugStringConvertible Implementations**
- **CustomReflectable Implementations**
- **CustomStringConvertible Implementations**
- **Decodable Implementations**
- **Encodable Implementations**
- **Equatable Implementations**
- **ExpressibleByArrayLiteral Implementations**
- **Hashable Implementations**
- **MutableCollection Implementations**
- **OperationParameter Implementations**
- **RandomAccessCollection Implementations**
- **RangeReplaceableCollection Implementations**
- **Sequence Implementations**