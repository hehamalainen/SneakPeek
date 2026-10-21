import Foundation
import Testing
@testable import SneakPeek
import SneakPeekCore

@Test @MainActor func largeTeamKeepsSelectionAndAttentionScopedToVisibleMission() throws {
    let json = #"{"generatedAt":1,"demo":false,"missions":[{"id":"one","title":"One","goal":"Inspect","checkpoints":[]},{"id":"two","title":"Two","goal":"Inspect","checkpoints":[]}],"agents":[{"id":"base","missionId":"one","name":"Worker","provider":"Codex","status":"working","summary":"Synthetic","lastActivity":1,"lastProgress":1,"evidence":"","nextStep":"Inspect","trajectory":"unknown"}]}"#
    var feed = try JSONDecoder().decode(Feed.self, from: Data(json.utf8))
    let template = feed.agents[0]
    feed.agents = (0..<1000).map { index in
        var agent = template
        agent.id = "worker-\(index)"
        agent.lastActivity = Double(index)
        agent.missionId = index < 900 ? "one" : "two"
        agent.provider = index.isMultiple(of: 2) ? "Codex" : "Claude"
        agent.status = index == 2 || index == 903 ? "attention" : "working"
        return agent
    }
    let store = PeekStore(stateURL: URL(fileURLWithPath: "/synthetic/state.json"), demo: false,
                          ownsApprovalSurface: false, automaticReload: false, readInitialFeed: false)
    store.feed = feed
    store.selectedMissionId = "one"
    #expect(store.agents.count == 900)
    #expect(store.agents.first?.id == "worker-2")
    #expect(store.selectedAgent?.id == "worker-2")
    store.selectedAgentId = "worker-4"
    #expect(store.selectedAgent?.id == "worker-4")

    store.filterProvider("Claude")
    #expect(store.agents.count == 450)
    #expect(store.agents.first?.id == "worker-899")
    #expect(store.selectedAgent == nil) // The Codex attention item cannot leak into this source.
    store.selectedMissionId = "two"
    #expect(store.agents.count == 50)
    #expect(store.selectedAgent?.id == "worker-903")
    store.selectedAgentId = "worker-999"
    #expect(store.selectedAgent?.id == "worker-999")
    store.selectedMissionId = "removed-mission"
    #expect(store.mission?.id == "one")
    #expect(store.selectedAgent == nil) // Removed/hidden selections fall back within the current mission.
}
