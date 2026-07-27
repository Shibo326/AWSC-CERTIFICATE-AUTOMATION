#!/bin/bash
# =============================================================================
# CertFlow macOS Build Script
# =============================================================================
#
# This script builds the CertFlow app as a native macOS application (.app bundle)
# using `flet build macos`. It optionally handles code signing and notarization.
#
# Prerequisites:
#   1. macOS with Xcode installed (xcode-select --install for command-line tools)
#   2. Python 3.11+ installed
#   3. Flet installed: pip install flet
#   4. Flutter SDK installed and in PATH
#      Download: https://docs.flutter.dev/get-started/install/macos
#   5. For code signing: Apple Developer ID certificate in Keychain
#   6. For notarization: App-specific password stored in Keychain
#
# Usage:
#   ./build_macos.sh              Build without code signing
#   ./build_macos.sh --sign       Build with code signing
#   ./build_macos.sh --notarize   Build with code signing and notarization
#
# Environment Variables (for code signing/notarization):
#   CERTFLOW_DEVELOPER_ID    - Developer ID Application certificate name
#                              Example: "Developer ID Application: Your Name (TEAMID)"
#   CERTFLOW_APPLE_ID        - Apple ID email for notarization
#   CERTFLOW_TEAM_ID         - Apple Developer Team ID (10-char alphanumeric)
#   CERTFLOW_NOTARY_PROFILE  - Notarytool keychain profile name
#                              (created with: xcrun notarytool store-credentials)
#
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
BUILD_OUTPUT_DIR="$PROJECT_DIR/build/macos"
APP_NAME="CertFlow"
BUNDLE_ID="com.certflow.app"

# Read version from pyproject.toml
VERSION=$(grep -m1 'version = ' "$PROJECT_DIR/pyproject.toml" | sed 's/version = "//;s/"//')
BUILD_NUMBER=$(date +%Y%m%d%H%M)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for macOS
    if [[ "$(uname)" != "Darwin" ]]; then
        log_error "This script must be run on macOS."
        exit 1
    fi

    # Check for Xcode command-line tools
    if ! xcode-select -p &>/dev/null; then
        log_error "Xcode command-line tools not installed."
        log_error "Install with: xcode-select --install"
        exit 1
    fi

    # Check for flet
    if ! command -v flet &>/dev/null; then
        log_error "flet command not found. Install with: pip install flet"
        exit 1
    fi

    # Check for flutter (required by flet build)
    if ! command -v flutter &>/dev/null; then
        log_warn "Flutter SDK not found in PATH. flet build may install it automatically."
    fi

    log_info "Prerequisites OK."
}

# =============================================================================
# Build Phase
# =============================================================================

build_macos() {
    log_info "Building CertFlow for macOS..."
    log_info "  Version: $VERSION"
    log_info "  Build Number: $BUILD_NUMBER"
    log_info "  Bundle ID: $BUNDLE_ID"
    log_info "  Min macOS: 12.0 (Monterey)"

    cd "$PROJECT_DIR"

    # Run flet build macos
    # --project: Flutter project name (lowercase, no spaces)
    # --product: Display name shown to users
    # --org: Organization identifier prefix
    # --build-version: Version string (e.g., "2.0.0")
    # --build-number: Integer build number for this release
    # -o: Output directory
    flet build macos \
        --project certflow \
        --product "$APP_NAME" \
        --org com.certflow \
        --build-version "$VERSION" \
        --build-number "$BUILD_NUMBER" \
        -o build

    if [ $? -eq 0 ]; then
        log_info "Build completed successfully!"
        log_info "Output: $BUILD_OUTPUT_DIR/$APP_NAME.app"
    else
        log_error "Build failed! Check the output above for details."
        exit 1
    fi

    # Check build size
    if [ -d "$BUILD_OUTPUT_DIR/$APP_NAME.app" ]; then
        BUILD_SIZE=$(du -sm "$BUILD_OUTPUT_DIR/$APP_NAME.app" | cut -f1)
        log_info "Build size: ${BUILD_SIZE}MB"
        if [ "$BUILD_SIZE" -gt 120 ]; then
            log_warn "Build exceeds 120MB target size (${BUILD_SIZE}MB)."
            log_warn "Consider reducing bundled assets."
        fi
    fi
}

# =============================================================================
# Code Signing Phase
# =============================================================================
#
# Code signing is required for:
#   - Distribution outside the Mac App Store (Developer ID)
#   - Passing macOS Gatekeeper without user override
#   - Notarization (Apple requires signed apps)
#
# Setup steps:
#   1. Enroll in Apple Developer Program ($99/year)
#   2. Create a "Developer ID Application" certificate at developer.apple.com
#   3. Download and install the certificate in Keychain Access
#   4. Set CERTFLOW_DEVELOPER_ID to the certificate's common name
#
# =============================================================================

sign_app() {
    local app_path="$BUILD_OUTPUT_DIR/$APP_NAME.app"

    if [ -z "${CERTFLOW_DEVELOPER_ID:-}" ]; then
        log_error "CERTFLOW_DEVELOPER_ID environment variable not set."
        log_error "Set it to your Developer ID Application certificate name."
        log_error "Example: export CERTFLOW_DEVELOPER_ID=\"Developer ID Application: Your Name (TEAMID)\""
        exit 1
    fi

    log_info "Code signing $APP_NAME.app..."
    log_info "  Certificate: $CERTFLOW_DEVELOPER_ID"

    # Sign the app bundle with hardened runtime (required for notarization)
    # --deep: Sign all nested code (frameworks, helpers)
    # --force: Replace any existing signature
    # --options runtime: Enable hardened runtime (required for notarization)
    # --entitlements: Apply our entitlements file
    # --timestamp: Include a secure timestamp (required for notarization)
    codesign --deep --force \
        --options runtime \
        --entitlements "$PROJECT_DIR/macos/CertFlow.entitlements" \
        --sign "$CERTFLOW_DEVELOPER_ID" \
        --timestamp \
        "$app_path"

    if [ $? -eq 0 ]; then
        log_info "Code signing successful!"

        # Verify the signature
        log_info "Verifying signature..."
        codesign --verify --deep --strict "$app_path"
        if [ $? -eq 0 ]; then
            log_info "Signature verification passed."
        else
            log_error "Signature verification failed!"
            exit 1
        fi
    else
        log_error "Code signing failed!"
        exit 1
    fi
}

# =============================================================================
# Notarization Phase
# =============================================================================
#
# Notarization is required for:
#   - Apps distributed outside the Mac App Store on macOS 10.15+
#   - Passing Gatekeeper without user override (right-click -> Open workaround)
#   - Proving to Apple your app is free of malware
#
# Setup steps:
#   1. Create an app-specific password at appleid.apple.com
#   2. Store credentials with notarytool:
#      xcrun notarytool store-credentials "certflow-notary" \
#        --apple-id "your-apple-id@example.com" \
#        --team-id "YOUR_TEAM_ID" \
#        --password "your-app-specific-password"
#   3. Set CERTFLOW_NOTARY_PROFILE="certflow-notary"
#
# The process:
#   1. ZIP the signed .app
#   2. Submit ZIP to Apple's notary service
#   3. Wait for Apple to scan and approve (usually 5-15 minutes)
#   4. Staple the notarization ticket to the .app
#   5. The app now passes Gatekeeper on any Mac
#
# =============================================================================

notarize_app() {
    local app_path="$BUILD_OUTPUT_DIR/$APP_NAME.app"
    local zip_path="$BUILD_OUTPUT_DIR/$APP_NAME.zip"

    if [ -z "${CERTFLOW_NOTARY_PROFILE:-}" ]; then
        log_error "CERTFLOW_NOTARY_PROFILE environment variable not set."
        log_error "Create a notarytool profile first:"
        log_error "  xcrun notarytool store-credentials \"certflow-notary\" \\"
        log_error "    --apple-id \"your-apple-id@example.com\" \\"
        log_error "    --team-id \"YOUR_TEAM_ID\" \\"
        log_error "    --password \"your-app-specific-password\""
        log_error "Then: export CERTFLOW_NOTARY_PROFILE=\"certflow-notary\""
        exit 1
    fi

    log_info "Preparing for notarization..."

    # Create ZIP for submission
    log_info "Creating ZIP archive..."
    ditto -c -k --keepParent "$app_path" "$zip_path"

    # Submit to Apple's notary service
    log_info "Submitting to Apple notary service (this may take 5-15 minutes)..."
    xcrun notarytool submit "$zip_path" \
        --keychain-profile "$CERTFLOW_NOTARY_PROFILE" \
        --wait

    if [ $? -eq 0 ]; then
        log_info "Notarization successful!"

        # Staple the notarization ticket to the app
        log_info "Stapling notarization ticket..."
        xcrun stapler staple "$app_path"

        if [ $? -eq 0 ]; then
            log_info "Stapling successful! App is ready for distribution."
        else
            log_error "Stapling failed! The app is notarized but the ticket is not attached."
            log_error "Users will need internet on first launch for Gatekeeper to verify."
            exit 1
        fi

        # Clean up ZIP
        rm -f "$zip_path"
    else
        log_error "Notarization failed!"
        log_error "Check the notarization log with:"
        log_error "  xcrun notarytool log <submission-id> --keychain-profile \"$CERTFLOW_NOTARY_PROFILE\""
        rm -f "$zip_path"
        exit 1
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    local do_sign=false
    local do_notarize=false

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --sign)
                do_sign=true
                ;;
            --notarize)
                do_sign=true
                do_notarize=true
                ;;
            --help|-h)
                echo "Usage: $0 [--sign] [--notarize]"
                echo ""
                echo "Options:"
                echo "  --sign       Code sign the app with Developer ID certificate"
                echo "  --notarize   Code sign and submit to Apple notarization service"
                echo "  --help       Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown argument: $arg"
                echo "Usage: $0 [--sign] [--notarize]"
                exit 1
                ;;
        esac
    done

    echo "============================================="
    echo "  CertFlow macOS Build"
    echo "  Version: $VERSION (build $BUILD_NUMBER)"
    echo "============================================="
    echo ""

    # Check prerequisites
    check_prerequisites

    # Build
    build_macos

    # Sign (if requested)
    if [ "$do_sign" = true ]; then
        sign_app
    else
        log_warn "Skipping code signing. Use --sign to sign the app."
        log_warn "Unsigned apps will trigger Gatekeeper warnings on other Macs."
    fi

    # Notarize (if requested)
    if [ "$do_notarize" = true ]; then
        notarize_app
    elif [ "$do_sign" = true ]; then
        log_warn "Skipping notarization. Use --notarize for full distribution readiness."
    fi

    # Final summary
    echo ""
    echo "============================================="
    echo "  Build Summary"
    echo "============================================="
    echo "  App: $BUILD_OUTPUT_DIR/$APP_NAME.app"
    echo "  Version: $VERSION"
    echo "  Build: $BUILD_NUMBER"
    echo "  Signed: $do_sign"
    echo "  Notarized: $do_notarize"
    echo "============================================="

    if [ "$do_sign" = true ] && [ "$do_notarize" = true ]; then
        log_info "App is fully signed and notarized — ready for distribution!"
    elif [ "$do_sign" = true ]; then
        log_info "App is signed but not notarized."
        log_info "Run with --notarize for Gatekeeper-ready distribution."
    else
        log_info "Build complete (unsigned). For distribution, run with --notarize."
    fi
}

main "$@"
