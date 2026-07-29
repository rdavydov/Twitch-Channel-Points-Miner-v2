from types import GenericAlias, MappingProxyType, NoneType, UnionType
from typing import Any, Callable, TypeAliasType, get_args

# Type representing an arbitrary Type Hint
type TypeHint[T] = type[T] | UnionType | TypeAliasType | Any
# An indexer to a dict or list
type Index = str | int
# A union of indexed types
type Indexable = dict | list


# TODO At some point, possibly in python 3.14, PEP747 will get implemented and we can get better type inference


def type_name(t: TypeHint) -> str:
    if type(t) is UnionType:
        return f"Union[{', '.join(i.__name__ for i in get_args(t))}]"
    else:
        return t.__name__


class DecoderError(Exception):
    """Base class for exceptions raised during JSON decoding."""

    def __init__(self, property_path: list[Index]):
        self.property_path = property_path
        """A list of indexers (string or int) that represent where the property that caused the error is in the root data structure."""

    def describe_path(self) -> str:
        """
        Describes the path of the property as a string.
        :return: The path.
        """
        return "".join(
            map(
                lambda path: f'["{path}"]' if isinstance(path, str) else f"[{path}]",
                reversed(self.property_path),
            )
        )

    def message(self) -> str:
        """A string representation of this error."""
        return ""

    def chain(self, index: Index):
        """Adds a value to this error's property path."""
        self.property_path.append(index)

    def __repr__(self):
        return self.message()

    def __str__(self):
        return self.message()


class InvalidValueError(DecoderError):
    def __init__(self, property_path: list[Index], value: Any):
        self.value = value
        super().__init__(property_path)

    def message(self) -> str:
        return f"Invalid value for property at {self.describe_path()}: type: {type(self.value).__name__}, value: {self.value}"


class NonExistentProperty(DecoderError):
    """An error that occurs when a property cannot be found."""

    def __init__(self, property_path: list[Index], property_type: TypeHint):
        self.property_type = property_type
        """The type of the property."""
        super().__init__(property_path)

    def message(self) -> str:
        return f'Unable to find "{type_name(self.property_type)}" property located at {self.describe_path()}.'


class WrongTypeError(DecoderError):
    """An error that occurs when the value of a property doesn't match the expected type."""

    def __init__(
        self, property_path: list[Index], property_type: TypeHint, actual_value: Any
    ):
        self.property_type = property_type
        self.actual_value = actual_value
        super().__init__(property_path)

    def message(self) -> str:
        return f'Property "{self.actual_value}" of type {type(self.actual_value).__name__} at {self.describe_path()} has the wrong type, expected "{type_name(self.property_type)}"'


class UnmappedTypeError(DecoderError):
    """An error that occurs when a mapper for the given result type cannot be found."""

    def __init__(self, property_path: list[Index], property_type: TypeHint):
        self.property_type = property_type
        """The type of the property."""
        super().__init__(property_path)

    def message(self) -> str:
        return f'Attempted to decode property at {self.describe_path()} but it\'s Type "{type_name(self.property_type)}" has no object mapper.'


class UnionParseError(DecoderError):
    """An error that occurs when all decoders for a union type fail."""

    def __init__(
        self,
        property_path: list[Index],
        expected_type: TypeHint,
        errors: list[DecoderError],
    ):
        self.expected_type = expected_type
        self.errors = errors
        super().__init__(property_path)

    def message(self) -> str:
        return f'Attempted to decode property at {self.describe_path()} as a Union type "{type_name(self.expected_type)}" but all sub decoders failed:\n{self.errors}"'


class DecoderIndexError(DecoderError):
    def __init__(self, index: Index, data: Any):
        self.data = data
        super().__init__([index])

    def message(self) -> str:
        return f"Attempted to find a property at {self.describe_path()} in data of type {type_name(type(self.data))} using indexer of type {type_name(type(self.property_path[0]))}"


type Decoder[Input, Output] = Callable[[JSONDictDecoder, Input], Output]


def instance_of_validator[T](value: Any, expected_type: TypeHint[T]) -> T:
    """
    A simple validator that expects the given value to already be a given type.

    Note that a limitation of Python's type hints means you cannot pass a generic type to expected_type.

    :param value: The value to validator.
    :param expected_type: The expected type of value.
    :return: The original value.
    :raises WrongTypeError: If the given value is not the expected type.
    """
    if expected_type is not TypeAliasType and isinstance(
        value, expected_type  # pyright: ignore [reportArgumentType]
    ):
        return value
    else:
        raise WrongTypeError([], expected_type, value)


def any_validator(_: "JSONDictDecoder", value: Any) -> Any:
    """
    A simple validator that always returns the given value.
    :param _: DecoderError that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated value.
    """
    return value


def none_validator(_: "JSONDictDecoder", value: Any) -> None:
    """
    A simple validator that expects the given value to be None.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated None.
    """
    return instance_of_validator(value, type(None))


def int_validator(_: "JSONDictDecoder", value: Any) -> int:
    """
    A simple validator that expects the given value to be an int.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated int.
    """
    if isinstance(value, bool):
        raise WrongTypeError([], int, value)
    return instance_of_validator(value, int)


def float_validator(_: "JSONDictDecoder", value: Any) -> float:
    """
    A simple validator that expects the given value to be a float.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated float.
    """
    return instance_of_validator(value, float)


def str_validator(_: "JSONDictDecoder", value: Any) -> str:
    """
    A simple validator that expects the given value to be a string.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated string.
    """
    return instance_of_validator(value, str)


def bool_validator(_: "JSONDictDecoder", value: Any) -> bool:
    """
    A simple validator that expects the given value to be a boolean.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated boolean.
    """
    return instance_of_validator(value, bool)


def dict_validator(_: "JSONDictDecoder", value: Any) -> dict:
    """
    A simple validator that expects the given value to be a dictionary.

    :param _: Decoder that could be used to decode child values.
    :param value: The value to validate.
    :return: The validated dictionary.
    """
    return instance_of_validator(value, dict)


def expect_type_and_map[
    Input, Output
](
    context: "JSONDictDecoder",
    value: Any,
    expect: type[Input],
    mapper: Callable[[Input], Output],
) -> Output:
    """
    A decoder that decodes the value as the Input type, then maps that value using the given mapper function into the Output type.

    :param context: The decoder that is used to decode child values.
    :param value: The value to decode.
    :param expect: The expected type of value.
    :param mapper: A function that maps the given value to the expected type.
    :return: The decoded and mapped value.
    """
    return mapper(context.decode(value, expect))


class Undefined(object):
    """Unique type representing a JSON undefined value."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance


class JSONDictDecoder:
    """
    A class that decodes JSON dicts into Python objects.
    For example, you can decode the result of json.loads().
    """

    default_decoders: MappingProxyType[TypeHint, Decoder] = MappingProxyType[
        TypeHint, Decoder
    ](
        {
            Any: any_validator,
            NoneType: none_validator,
            int: int_validator,
            float: float_validator,
            str: str_validator,
            bool: bool_validator,
            dict: dict_validator,
        }
    )
    """Default decoders for JSONDictDecoders."""

    def __init__(self, decoders: dict[TypeHint, Decoder] | None = None):
        self.__decoders = dict(
            decoders if decoders is not None else self.default_decoders
        )
        """
        Functions that can can be used to decode specific types.
        In order to get nicely formatted errors, decoders should raise DecoderErrors.
        """

    def with_decoder(self, t: TypeHint, decoder: Decoder) -> "JSONDictDecoder":
        """Sets the decoder for the given type."""
        self.__decoders[t] = decoder
        return self

    def with_decoders(self, decoders: dict[TypeHint, Decoder]) -> "JSONDictDecoder":
        """Sets the decoders for the given types."""
        for t, decoder in decoders.items():
            self.__decoders[t] = decoder
        return self

    def __decode_union(self, data: Any, expected: TypeHint):
        """
        Attempts to decode the given data into the given union type.
        TODO TypeForm should allow us to specify the return type properly.

        :param data: The data to decode.
        :param expected: The expected type of the data.
        :return: The decoded result.
        :raises DecoderError: If the given data is not a union type.
        """
        if isinstance(expected, UnionType):
            errors = []
            for possible_type in get_args(expected):
                try:
                    return self.decode(data, possible_type)
                except UnmappedTypeError as e:
                    raise e
                except DecoderError as e:
                    errors.append(e)
                    continue
            # Ignore warning, this is fine
            raise UnionParseError([], expected, errors)
        else:
            raise WrongTypeError([], expected, type(data))

    def decode_list[
        Result
    ](self, data_list: list[Any], result_type: TypeHint[Result]) -> list[Result]:
        """
        Attempts to decode the given data into a list of the given type.

        :param data_list: The data to decode as a list.
        :param result_type: The expected type of the items in the list.
        :return: The decoded list.
        :raises ParseError: If the list cannot be decoded.
        """
        return [
            self.__decode_property(data_list, property_index, result_type)
            for property_index in range(len(data_list))
        ]

    def decode_dict[
        Result
    ](self, data: dict[str, Any], result_type: TypeHint[Result]) -> dict[str, Result]:
        """
        Attempts to decode the given data dict[str, Any] into a dict[str, Result].

        :param data: The data to decode as a dict.
        :param result_type: The result type of the decoded items.
        :return: The decoded dict.
        """
        return {
            key: self.__decode_property(data, key, result_type) for key in data.keys()
        }

    def decode[Result](self, data: Any, result_type: TypeHint[Result]) -> Result:
        """
        Attempts to decode the given data into the given type.

        :param data: The data to decode.
        :param result_type: The result type of the data.
        :return: The decoded data.
        :raises ParseError: If the property cannot be decoded.
        """
        if isinstance(result_type, UnionType):
            return self.__decode_union(data, result_type)
        elif isinstance(result_type, GenericAlias) and result_type.__origin__ is list:
            list_args = get_args(result_type)
            if len(list_args) == 1:
                return self.decode_list(
                    data, list_args[0]
                )  # pyright: ignore [reportReturnType]
            else:
                raise WrongTypeError([], result_type, type(data))
        elif isinstance(result_type, dict):
            dict_args = get_args(result_type)
            if len(dict_args) == 2:
                return self.decode_dict(
                    data, dict_args[1]
                )  # pyright: ignore [reportReturnType]
            else:
                raise WrongTypeError([], result_type, type(data))
        else:
            mapper = self.__decoders.get(result_type, None)
            if mapper is None:
                raise UnmappedTypeError([], result_type)
            else:
                return mapper(self, data)

    @staticmethod
    def __get_property[
        Result
    ](data: Indexable, path: Index, result_type: TypeHint[Result]) -> Any:
        if isinstance(data, dict) and isinstance(path, str):
            if path not in data:
                raise NonExistentProperty([path], result_type)
            return data[path]
        elif isinstance(data, list) and isinstance(path, int):
            if path < 0 or path >= len(data):
                raise NonExistentProperty([path], result_type)
            return data[path]
        else:
            raise DecoderIndexError(path, data)

    def __decode_optional_property[
        Result
    ](
        self,
        data: Indexable,
        path: Index,
        result_type: TypeHint[Result],
        optional=False,
    ) -> (Result | Undefined):
        try:
            prop = self.__get_property(data, path, result_type)
        except NonExistentProperty:
            if optional:
                return Undefined()
            else:
                raise
        try:
            return self.decode(prop, result_type)
        except DecoderError as e:
            e.chain(path)
            raise e

    def __decode_property[
        Result
    ](
        self,
        data: Indexable,
        path: Index,
        result_type: TypeHint[Result],
        optional=False,
    ) -> Result:
        prop = self.__get_property(data, path, result_type)
        try:
            return self.decode(prop, result_type)
        except DecoderError as e:
            e.chain(path)
            raise e

    def decode_property_from_list[
        Result
    ](self, data: list[Any], path: int, result_type: TypeHint[Result]) -> list[Result]:
        """
        Attempts to decode a property from a list of the given type.

        :param data: The parent list to decode.
        :param path: The path of the property in the list, it's index.
        :param result_type: The result type of the property.
        :return: The decoded property.
        """
        return self.__decode_property(data, path, result_type)

    def decode_property[
        Result
    ](self, data: dict[str, Any], path: str, result_type: TypeHint[Result]) -> Result:
        """
        Attempts to decode a property value at the given path in the given data.

        :param data: The parent of the value to decode.
        :param path: The path of the property to decode.
        :param result_type: The result type of the property value.
        :return: The decoded value.
        :raises ParseError: If the property cannot be decoded.
        """
        return self.__decode_property(data, path, result_type)

    def decode_optional_property[
        Result
    ](self, data: dict[str, Any], path: str, result_type: TypeHint[Result]) -> (
        Result | Undefined
    ):
        """
        Attempts to decode an optional property value at the given path in the given data.
        If the property doesn't exist in the dict, i.e. the json property was undefined, an instance of the special Undefined type will be returned.

        :param data: The parent of the value to decode.
        :param path: The path of the property to decode.
        :param result_type: The result type of the property value.
        :return: The decoded value or undefined.
        :raises ParseError: If the property cannot be decoded.
        """
        return self.__decode_optional_property(data, path, result_type, True)
