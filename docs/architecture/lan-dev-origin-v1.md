# LAN Next.js development origin v1

## Purpose

The local LineAlert UI is intentionally reachable from a second machine on the
same LAN through port 8766. Next.js development mode protects its development
resources, including HMR, with an allowed-origin check.

During live emulated historian acceptance, the laptop could load the initial
page shell from 192.168.0.242:8766, but the Next.js server logged:

Blocked cross-origin request to Next.js dev resource /_next/hmr from 192.168.0.242.

This prevented the LAN browser from reliably completing the client-side runtime
needed for polling. The historian emulator itself remained healthy.

## Bounded fix

The hybrid launcher now resolves one LAN IPv4 address from the Windows default
IPv4 route. Unless an explicit LINEALERT_UI_ALLOWED_DEV_ORIGIN value is already
supplied, that address is exported to the Next.js process.

ui/next.config.ts reads that single value and passes it as allowedDevOrigins.

There is no wildcard origin and no subnet-wide allow rule.

On the current host the derived address is 192.168.0.242.

## Network boundary

This change affects only Next.js development-resource origin validation on the
UI process at port 8766.

It does not change the listener bindings of the internal services:

- historian / historian emulator: 127.0.0.1:8767
- service-case persistence: 127.0.0.1:8768

The laptop continues to use the same-origin Next.js API on 8766. It does not
gain direct access to either loopback service.

## Fallback and override

If no usable default-route IPv4 address can be resolved, the launcher leaves
the extra allowed development origin unset and Next.js retains its default
behavior.

An operator may set LINEALERT_UI_ALLOWED_DEV_ORIGIN explicitly before launching
the local stack to override automatic detection for a known development host.

## Runtime acceptance

On the current host, the launcher derived `192.168.0.242` and reported it as the allowed Next.js LAN development origin. A WebSocket request to `ws://192.168.0.242:8766/_next/hmr` with Origin `http://192.168.0.242:8766` reached `Open` state, and the bounded acceptance log did not emit the prior blocked-origin warning. The Reasoning Inputs initial HTML simultaneously returned HTTP 200 with live-emulation state.

## Boundaries

- lan_dev_origin_allowance != historian_lan_binding
- lan_dev_origin_allowance != service_case_store_lan_binding
- browser_hmr_access != equipment_access
- browser_client_polling != historian_authority
- network_reachability != production_authorization

## Rollback

Revert the Next.js allowedDevOrigins configuration and launcher origin
derivation. The server-rendered Reasoning Inputs fallback remains independently
capable of showing the current snapshot without client hydration.
