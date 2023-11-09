ROBOTMK := robotmk

ROBOTMK_BUILD := $(BUILD_HELPER_DIR)/$(ROBOTMK)-build
ROBOTMK_INTERMEDIATE_INSTALL := $(BUILD_HELPER_DIR)/$(ROBOTMK)-install-intermediate
ROBOTMK_INSTALL := $(BUILD_HELPER_DIR)/$(ROBOTMK)-install

ROBOTMK_INSTALL_DIR := $(INTERMEDIATE_INSTALL_BASE)/$(ROBOTMK)
ROBOTMK_BAZEL_OUT := $(BAZEL_BIN_EXT)/$(ROBOTMK)

.PHONY: $(ROBOTMK_BUILD)
$(ROBOTMK_BUILD):
	$(BAZEL_BUILD) @$(ROBOTMK)//:build

.PHONY: $(ROBOTMK_INTERMEDIATE_INSTALL)
$(ROBOTMK_INTERMEDIATE_INSTALL): $(ROBOTMK_BUILD)
	$(MKDIR) $(ROBOTMK_INSTALL_DIR)/share/check_mk/agents/windows/plugins
	install -m 755 $(ROBOTMK_BAZEL_OUT)/robotmk.exe $(ROBOTMK_BAZEL_OUT)/rcc.exe $(ROBOTMK_INSTALL_DIR)/share/check_mk/agents/windows
	install -m 755 $(ROBOTMK_BAZEL_OUT)/robotmk_agent.exe $(ROBOTMK_INSTALL_DIR)/share/check_mk/agents/windows/plugins

.PHONY: $(ROBOTMK_INSTALL)
$(ROBOTMK_INSTALL): $(ROBOTMK_INTERMEDIATE_INSTALL)
	$(RSYNC) $(ROBOTMK_INSTALL_DIR)/ $(DESTDIR)$(OMD_ROOT)/
