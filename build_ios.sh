#!/usr/bin/env bash
# =============================================================================
# CertFlow iOS Build Script
# =============================================================================
# Builds the CertFlow app as an iOS .ipa using flet build ipa.
#
# Prerequisites:
#   1. macOS with Xcode 15+ installed
#   2. Valid Apple Developer account
#   3. Provisioning profile and signing certificate configured (see ios/README.md)
#   4. Python 3.11+ with flet installed: pip install flet
#   5. Flutter SDK installed and in PATH
#   6. CocoaPods installed: sudo gem install cocoapods
#
# Usage:
#   ./build_ios.sh                  # Build with default settings
#   ./build_ios.sh --no-codesign    # Build without code signing (for CI dry runs)
#
# Environment Variables (optional):
#   CERTFLOW_IOS_TEAM_ID            - Apple Developer Team ID
#   CERTFLOW_IOS_PROVISIONING       - Path to provisioning profile (.mobileprovision)
#   CERTFLOW_IOS_SIGNING_IDENTITY   - Code signing identity (e.g., "Apple Distribution: ...")
#
# =============================================================================

set -euo pipefail

# Configuration
PROJECT_NAME="certflow"
PRODUCT_NAME="CertFlow"
ORG="com.certflow"
BUNDLE_ID="com.certflow.app"
BUILD_OUTPUT="build"
MIN_IOS_VERSION="16.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse version from pyproject.toml
VERSION=$(grep -m1 'version = ' pyproject.toml | sed 's/version = "//;s/"//')
BUILD_NUMBER=$(date +%Y%m%d%H%M)

echo "=============================================="
echo "  CertFlow iOS Build"
echo "  Version: ${VERSION} (build ${BUILD_NUMBER})"
echo "  Bundle ID: ${BUNDLE_ID}"
echo "  Min iOS: ${MIN_IOS_VERSION}"
echo "=============================================="
echo ""

# --- Pre-flight checks ---

# Check we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}[ERROR] iOS builds require macOS with Xcode.${NC}"
    echo "        This script cannot run on $(uname)."
    exit 1
fi

# Check Xcode is installed
if ! command -v xcodebuild &> /dev/null; then
    echo -e "${RED}[ERROR] Xcode is not installed or xcodebuild is not in PATH.${NC}"
    echo "        Install Xcode from the Mac App Store and run:"
    echo "        sudo xcode-select --switch /Applications/Xcode.app"
    exit 1
fi

# Check flet is available
if ! command -v flet &> /dev/null; then
    echo -e "${RED}[ERROR] flet command not found.${NC}"
    echo "        Install with: pip install flet"
    exit 1
fi

# Check Flutter SDK
if ! command -v flutter &> /dev/null; then
    echo -e "${RED}[ERROR] Flutter SDK not found in PATH.${NC}"
    echo "        Download: https://docs.flutter.dev/get-started/install/macos"
    exit 1
fi

# Check CocoaPods
if ! command -v pod &> /dev/null; then
    echo -e "${YELLOW}[WARNING] CocoaPods not found. Installing...${NC}"
    sudo gem install cocoapods || {
        echo -e "${RED}[ERROR] Failed to install CocoaPods.${NC}"
        exit 1
    }
fi

echo -e "${GREEN}[OK] All prerequisites satisfied.${NC}"
echo ""

# --- Parse arguments ---
NO_CODESIGN=false
for arg in "$@"; do
    case $arg in
        --no-codesign)
            NO_CODESIGN=true
            echo -e "${YELLOW}[INFO] Code signing disabled (dry run mode).${NC}"
            ;;
    esac
done

# --- Signing configuration ---
if [[ "$NO_CODESIGN" == false ]]; then
    echo "[INFO] Checking signing configuration..."

    # Check for provisioning profile
    if [[ -n "${CERTFLOW_IOS_PROVISIONING:-}" ]]; then
        if [[ ! -f "$CERTFLOW_IOS_PROVISIONING" ]]; then
            echo -e "${RED}[ERROR] Provisioning profile not found: ${CERTFLOW_IOS_PROVISIONING}${NC}"
            echo "        Set CERTFLOW_IOS_PROVISIONING to a valid .mobileprovision file path."
            exit 1
        fi
        echo -e "${GREEN}  Provisioning profile: ${CERTFLOW_IOS_PROVISIONING}${NC}"
    else
        # Check for provisioning profiles in default location
        PROV_DIR="$HOME/Library/MobileDevice/Provisioning Profiles"
        if [[ -d "$PROV_DIR" ]] && ls "$PROV_DIR"/*.mobileprovision &> /dev/null 2>&1; then
            echo -e "${GREEN}  Provisioning profiles found in default location.${NC}"
        else
            echo -e "${RED}[ERROR] No provisioning profile configured.${NC}"
            echo ""
            echo "  Options:"
            echo "    1. Set CERTFLOW_IOS_PROVISIONING=/path/to/profile.mobileprovision"
            echo "    2. Install a profile via Xcode (Xcode > Settings > Accounts)"
            echo "    3. Use --no-codesign for a dry run without signing"
            echo ""
            echo "  See ios/README.md for detailed provisioning setup instructions."
            exit 1
        fi
    fi

    # Check signing identity
    if [[ -n "${CERTFLOW_IOS_SIGNING_IDENTITY:-}" ]]; then
        echo -e "${GREEN}  Signing identity: ${CERTFLOW_IOS_SIGNING_IDENTITY}${NC}"
    else
        # Check if any valid iOS signing identities exist in keychain
        if security find-identity -v -p codesigning 2>/dev/null | grep -q "iPhone"; then
            echo -e "${GREEN}  iOS signing identity found in keychain.${NC}"
        else
            echo -e "${RED}[ERROR] No iOS signing identity found in keychain.${NC}"
            echo ""
            echo "  Options:"
            echo "    1. Set CERTFLOW_IOS_SIGNING_IDENTITY=\"Apple Distribution: Your Name (TEAM_ID)\""
            echo "    2. Install your certificate via Xcode (Xcode > Settings > Accounts)"
            echo "    3. Use --no-codesign for a dry run without signing"
            echo ""
            echo "  See ios/README.md for certificate setup instructions."
            exit 1
        fi
    fi

    # Team ID
    if [[ -n "${CERTFLOW_IOS_TEAM_ID:-}" ]]; then
        echo -e "${GREEN}  Team ID: ${CERTFLOW_IOS_TEAM_ID}${NC}"
    else
        echo -e "${YELLOW}  [WARNING] CERTFLOW_IOS_TEAM_ID not set. Xcode will use the default team.${NC}"
    fi

    echo ""
fi

# --- Build ---
echo "[INFO] Running flet build ipa..."
echo ""

BUILD_CMD="flet build ipa"
BUILD_CMD+=" --project ${PROJECT_NAME}"
BUILD_CMD+=" --product ${PRODUCT_NAME}"
BUILD_CMD+=" --org ${ORG}"
BUILD_CMD+=" --build-version ${VERSION}"
BUILD_CMD+=" --build-number ${BUILD_NUMBER}"
BUILD_CMD+=" --description \"Bulk Certificate Generator and Email Sender\""
BUILD_CMD+=" -o ${BUILD_OUTPUT}"

if [[ "$NO_CODESIGN" == true ]]; then
    BUILD_CMD+=" --no-codesign"
fi

echo "  Command: ${BUILD_CMD}"
echo ""

# Execute build
eval $BUILD_CMD
BUILD_EXIT_CODE=$?

echo ""

# --- Report results ---
if [[ $BUILD_EXIT_CODE -eq 0 ]]; then
    echo "=============================================="
    echo -e "${GREEN}  [SUCCESS] iOS build complete!${NC}"
    echo "=============================================="
    echo ""
    echo "  Output: ${BUILD_OUTPUT}/ipa/"
    echo "  Version: ${VERSION} (build ${BUILD_NUMBER})"
    echo "  Bundle ID: ${BUNDLE_ID}"
    echo ""
    if [[ "$NO_CODESIGN" == false ]]; then
        echo "  Next steps:"
        echo "    1. Test on a physical device via Xcode or Apple Configurator"
        echo "    2. Upload to App Store Connect via Transporter or Xcode"
        echo "    3. Submit for TestFlight review"
    else
        echo "  Note: Build was created without code signing (--no-codesign)."
        echo "  Re-run without --no-codesign to produce a signed .ipa for distribution."
    fi
else
    echo "=============================================="
    echo -e "${RED}  [FAILED] iOS build failed (exit code: ${BUILD_EXIT_CODE})${NC}"
    echo "=============================================="
    echo ""
    echo "  Common issues:"
    echo "    - Invalid provisioning profile or expired certificate"
    echo "      Fix: Renew in Apple Developer portal, re-download profile"
    echo ""
    echo "    - Bundle ID mismatch with provisioning profile"
    echo "      Fix: Ensure profile is for '${BUNDLE_ID}'"
    echo ""
    echo "    - Missing Xcode command line tools"
    echo "      Fix: sudo xcode-select --install"
    echo ""
    echo "    - CocoaPods dependency resolution failure"
    echo "      Fix: cd build/ios && pod install --repo-update"
    echo ""
    echo "    - Flutter/Dart SDK version mismatch"
    echo "      Fix: flutter upgrade && flutter doctor"
    echo ""
    echo "  For full error details, check the build log above."
    exit $BUILD_EXIT_CODE
fi
