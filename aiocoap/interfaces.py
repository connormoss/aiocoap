# This file is part of the Python aiocoap library project.
#
# Copyright (c) 2012-2014 Maciej Wasilak <http://sixpinetrees.blogspot.com/>,
#               2013-2014 Christian Amsüss <c.amsuess@energyharvesting.at>
#
# aiocoap is free software, this file is published under the MIT license as
# described in the accompanying LICENSE file.

"""This module provides interface base classes to various aiocoap services,
especially with respect to request and response handling."""

import abc
from asyncio import coroutine

class TransportEndpoint(metaclass=abc.ABCMeta):
    """A MessageEndpoint (renaming pending) is an object that can exchange addressed messages over
    unreliable transports. Implementations send and receive messages with
    message type and message ID, and are driven by a Context that deals with
    retransmission.

    Usually, an MessageEndpoint refers to something like a local socket, and
    send messages to different remote endpoints depending on the message's
    addresses. Just as well, a MessageEndpoint can be useful for one single
    address only, or use various local addresses depending on the remote
    address.

    Next steps: Have it operated not by a Context, but by a
    RequestResponseEndpoint that is controlled by a thinner Context.
    """

    @abc.abstractmethod
    async def shutdown(self):
        """Deactivate the complete transport, usually irrevertably. When the
        coroutine returns, the object must have made sure that it can be
        destructed by means of ref-counting or a garbage collector run."""

    @abc.abstractmethod
    def send(self, message):
        """Send a given :class:`Message` object"""

    @abc.abstractmethod
    async def determine_remote(self, message):
        """Return a value suitable for the message's remote property based on
        its .opt.uri_host or .unresolved_remote.

        May return None, which indicates that the TransportEndpoint can not
        transport the message (typically because it is of the wrong scheme)."""

class EndpointAddress(metaclass=abc.ABCMeta):
    """An address that is suitable for routing through the application to a
    remote endpoint.

    Depending on the TransportEndpoint implementation used, an EndpointAddress
    property of a message can mean the message is exchanged "with
    [2001:db8::2:1]:5683, while my local address was [2001:db8:1::1]:5683"
    (typical of UDP6), "over the connected <Socket at
    0x1234>, whereever that's connected to" (simple6 or TCP) or "with
    participant 0x01 of the OSCAP key 0x..., routed over <another
    EndpointAddress>".

    EndpointAddresses are only concstructed by TransportEndpoint objects,
    either for incoming messages or when populating a message's .remote in
    :meth:`TransportEndpoint.determine_remote`.

    There is no requirement that those address are always identical for a given
    address. However, incoming addresses must be hashable and hash-compare
    identically to requests from the same context. The "same context", for the
    purpose of EndpointAddresses, means that the message must be eligible for
    request/response, blockwise (de)composition and observations. (For example,
    in a DTLS context, the hash must change between epochs due to RFC7252
    Section 9.1.2).

    So far, it is required that hash-identical objects also compare the same.
    That requirement might go away in future to allow equality to reflect finer
    details that are not hashed. (The only property that is currently known not
    to be hashed is the local address in UDP6, because that is *unknown* in
    initially sent packages, and thus disregarded for comparison but needed to
    round-trip through responses.)
    """

    @property
    @abc.abstractmethod
    def hostinfo(self):
        """The authority component of URIs that this endpoint represents"""

    @property
    @abc.abstractmethod
    # FIXME htis is so far only used in RD, might still need renaming
    def uri(self):
        """The base URI for this endpoint (typically scheme plus .hostinfo)"""

    @property
    @abc.abstractmethod
    def is_multicast(self):
        """True if the remote address is a multicast address, otherwise false."""

    @property
    @abc.abstractmethod
    def is_multicast_locally(self):
        """True if the local address is a multicast address, otherwise false."""

class MessageManager(metaclass=abc.ABCMeta):
    """The interface an entity that drives a TransportEndpoint provides towards
    the TransportEndpoint for callbacks and object acquisition."""

    @abc.abstractmethod
    def dispatch_message(self, message):
        """Callback to be invoked with an incoming message"""

    @abc.abstractmethod
    def dispatch_error(self, errno, remote):
        """Callback to be invoked when the operating system indicated an error
        condition from a particular remote.

        This interface is likely to change soon to something that is not
        limited to errno-style errors, and might allow transporting additional
        data."""

    @property
    @abc.abstractmethod
    def client_credentials(self):
        """A CredentialsMap that transports should consult when trying to
        establish a security context"""

class RequestProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def request(self, request_message):
        """Create and act on a a :class:`Request` object that will be handled
        according to the provider's implementation."""

class Request(metaclass=abc.ABCMeta):
    """A CoAP request, initiated by sending a message. Typically, this is not
    instanciated directly, but generated by a :meth:`RequestProvider.request`
    method."""

    response = """A future that is present from the creation of the object and \
        fullfilled with the response message."""

class Resource(metaclass=abc.ABCMeta):
    """Interface that is expected by a :class:`.protocol.Context` to be present
    on the serversite, which renders all requests to that context."""

    @abc.abstractmethod
    async def render(self, request):
        """Return a message that can be sent back to the requester.

        This does not need to set any low-level message options like remote,
        token or message type; it does however need to set a response code.

        The ``aiocoap.message.NoResponse`` sentinel can be returned if the
        resources wishes to suppress an answer on the request/response
        layer. (An empty ACK is sent responding to a CON request on message
        layer nevertheless.)"""

    @abc.abstractmethod
    async def needs_blockwise_assembly(self, request):
        """Indicator to the :class:`.protocol.Responder` about whether it
        should assemble request blocks to a single request and extract the
        requested blocks from a complete-resource answer (True), or whether
        the resource will do that by itself (False)."""

class ObservableResource(Resource, metaclass=abc.ABCMeta):
    """Interface the :class:`.protocol.ServerObservation` uses to negotiate
    whether an observation can be established based on a request.

    This adds only functionality for registering and unregistering observations;
    the notification contents will be retrieved from the resource using the
    regular :meth:`.render` method from crafted (fake) requests.
    """
    @abc.abstractmethod
    async def add_observation(self, request, serverobservation):
        """Before the incoming request is sent to :meth:`.render`, the
        :meth:`.add_observation` method is called. If the resource chooses to
        accept the observation, it has to call the
        `serverobservation.accept(cb)` with a callback that will be called when
        the observation ends. After accepting, the ObservableResource should
        call `serverobservation.trigger()` whenever it changes its state; the
        ServerObservation will then initiate notifications by having the
        request rendered again."""
