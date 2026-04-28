+++
title = 'Secured wireless communication between IoT devices with AWS greengrass Discovery'
date = '2026-04-28T11:00:00+09:00'
draft = false
tags = ['iot', 'aws']
+++
As a ML engineer working with IoT systems, I often have the need to make separate IoT devices communicate wirelessly together to be in sync. A sensor prototype running on one board needs to send its readings to a gateway device running the control logic. Or two sensor units need to synchronize their sampling without being wired together, or integrated with the same software.

The classic approach is to put everything on the same board, same codebase, same process. But this bring a number of challenges as you lose modularity, and every hardware change means refactoring everything. For such prototyping, in-house evaluation use cases what you really want is: independent devices, each running their own logic, communicating wirelessly over the local network with mutual authentication. No need to wire everything in the same board, but no cloud roundtrip either.

AWS Greengrass has a mechanism for exactly this, and it's surprisingly under-documented in my opinion, it is called **device discovery with local MQTT bridging**[^1].

## Concept
Say Device A is a sensor unit publishing readings every second on a local IPC topic. Device B is bigger system that need to now the device A sensor's state in real time. Both are Greengrass core devices, sitting on the same network.

The goal: Device B discovers Device A on the local network, authenticates using its IoT certificate, establishes a direct MQTT connection, and starts receiving messages. All local, all encrypted, no internet required after initial provisioning.

## How discovery works
Each Greengrass core device can act as a local MQTT broker (using Moquette) and advertise its endpoints to client devices. The flow goes like this:

1. The **client device** (data-receiving end) calls the Greengrass Discovery API[^2] with its own Thing Name
2. AWS returns a list of core devices it's authorized to connect to, along with their local IP addresses, ports, and group CA certificates
3. The client iterates through the discovered endpoints, attempts mTLS connections using its own certificate and the group CA
4. Once connected, it subscribes to MQTT topics and starts receiving messages

The nice part is that all it uses standard X.509 certificates already provisioned through AWS IoT Core[^3], so there is no extra security setting to perform.

![](/images/blog/iot-discovery.png)


## How to set this up
### Host device (data-emitting end)
The host needs four official Greengrass components deployed:

- **Client Device Auth**[^4]: defines authorization policies: which client things can connect, and what they can publish/subscribe to. You configure device groups with selection rules (e.g. match by thing name) and policies granting `mqtt:connect`, `mqtt:publish`, `mqtt:subscribe` permissions
- **IP Detector**: automatically detects and advertises the device's local IP endpoints so clients can find it
- **MQTT Bridge**[^5]: maps IPC topics to the local MQTT broker. This is the key piece: your component publishes to a local IPC topic like `local/bridge/sensor/output`, and the bridge makes it available to MQTT clients
- **Moquette**[^6]: the actual local MQTT broker that client devices connect to

After deployment, you associate client devices[^7] by their Thing Names in the AWS Console under the core device's client device settings.

### Client device (data-receiving end)

The client runs a **Discovery Bridge** component, that you can simply implement in your language of choice. The core logic you will need is as follows.

1. **Perform discovery** by using the `DiscoveryClient`[^8] from the AWS IoT SDK, passing in the device's certificate and key. Call `discover(thing_name)` to get the list of reachable core devices with their endpoints and group CAs
2. **Try endpoints**: iterate through discovered groups, cores, and connectivity info. For each, attempt an MQTT connection using `mqtt_connection_builder.mtls_from_path`, passing the endpoint's host/port and the group's CA certificate. Set appropriate timeouts and keepalive (longer is better here if your network can become unstable like mine)
3. **Bridge messages**: subscribe to `local/bridge/#` on each MQTT connection. When messages arrive from a remote core, republish them to the local IPC bus using `PublishToTopicRequest`. This way, local components on the client device can consume remote data as if it were local
4. **Handle the reverse**: also subscribe to `local/bridge/#` on the local IPC bus. When local components publish there, forward those messages to all connected MQTT cores. This gives you bidirectional bridging
5. **Recovery**: connections drop. The SDK handles short interruptions with auto-reconnect, but for longer outages (session lost, core device rebooted), I recommend a recovery loop that re-runs discovery and re-establishes connections

## testing
To verify the bridge works:
1. On the host device, have your component publish to both its normal IPC topic and a `local/bridge/...` mirror topic
2. On the client device, subscribe to the bridged topic and check data arrives
3. You can use the AWS CLI on the client device to subscribe and inspect messages[^9]

## closing thoughts
This setup has been useful for keeping prototyping modular: each sensor or compute unit stays independent, with its own deployment lifecycle, and they find each other on the network automatically. It's not the simplest thing to set up the first time, but once running it's been reliable. I have had arrays of more than 5 devices communicating between them and it clearly helped us speed up data collection!

If you're doing MLOps or embedded ML work and constantly rewiring how devices talk to each other, having a generic discovery bridge sitting in your deployment toolkit is a huge help.

## playlist
- Yonin Bayashi - Omatsuri
- Tears for Fears - Suffer the Children
- Christophe Laurent - Nuits Brésiliennes

[^1]: [Connect client devices to core devices](https://docs.aws.amazon.com/greengrass/v2/developerguide/connect-client-devices.html)
[^2]: [Greengrass Discovery RESTful API](https://docs.aws.amazon.com/greengrass/v2/developerguide/greengrass-discover-api.html)
[^3]: [Device authentication and authorization for AWS IoT Greengrass](https://docs.aws.amazon.com/greengrass/v2/developerguide/device-auth.html)
[^4]: [Client device auth component](https://docs.aws.amazon.com/greengrass/v2/developerguide/client-device-auth-component.html)
[^5]: [MQTT bridge component](https://docs.aws.amazon.com/greengrass/v2/developerguide/mqtt-bridge-component.html)
[^6]: [Moquette MQTT 3.1.1 broker component](https://docs.aws.amazon.com/greengrass/v2/developerguide/mqtt-broker-moquette-component.html)
[^7]: [Associate client devices with a core device](https://docs.aws.amazon.com/greengrass/v2/developerguide/associate-client-devices.html)
[^8]: [DiscoveryClient: AWS IoT Device SDK v2 for Python](https://aws.github.io/aws-iot-device-sdk-python-v2/awsiot/greengrass_discovery.html)
[^9]: [Test client device communications](https://docs.aws.amazon.com/greengrass/v2/developerguide/test-client-device-communications.html)
